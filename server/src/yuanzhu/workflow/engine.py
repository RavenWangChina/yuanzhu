"""工作流执行引擎（spec 3.2：steps = action_step | ai_step | query_step）

- ai_step 提示词分区（ADR-008）：稳定前缀（模板内 prompt_prefix，缓存友好）
  + 可变段（prompt_var 绑定的运行时数据），只发可变段给模型、前缀由引擎拼接
- action_step 走 staged 状态机（写低；L1 自动、L2+ 人审）
- query_step 查本体对象（读高）
- 变量绑定：$params.x（入参）/ $output（上游步骤输出）/ $item.x（迭代项）
"""
import json
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from yuanzhu.db.models import Template
from yuanzhu.staged.state_machine import StagedStateMachine
from yuanzhu.ontology.object_store import ObjectStore
from yuanzhu.ontology.action_store import ActionStore


async def call_model(model: str, prompt: str) -> str:
    """ai_step 的模型调用（经网关；测试被 monkeypatch 替换）"""
    from yuanzhu.gateway.proxy import acompletion
    response = await acompletion(
        model=model,
        messages=[{"role": "user", "content": prompt}],
    )
    data = response if isinstance(response, dict) else response.model_dump()
    return data["choices"][0]["message"]["content"]


class WorkflowEngine:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.sm = StagedStateMachine(session)
        self.object_store = ObjectStore(session)
        self.action_store = ActionStore(session)

    async def run(
        self, domain: str, workflow_name: str,
        params: Dict[str, Any], run_by: str,
    ) -> Dict[str, Any]:
        """顺序执行工作流（v0.1：无并行/无分支——spec 边界）"""
        workflow = await self._load_workflow(domain, workflow_name)

        context: Dict[str, Any] = {"params": params}
        step_results: Dict[str, Any] = {}

        for step in workflow.get("steps", []):
            step_id = step["id"]
            step_type = step.get("type")

            if step_type == "query_step":
                step_results[step_id] = await self._query_step(step)

            elif step_type == "ai_step":
                step_results[step_id] = await self._ai_step(step, context)

            elif step_type == "action_step":
                step_results[step_id] = await self._action_step(step, context, run_by)

            else:
                raise ValueError(f"未知步骤类型: {step_type}（v0.1 支持 action/ai/query）")

            # 上游输出进上下文（output 名绑定）
            if step.get("output"):
                context[step["output"]] = (
                    step_results[step_id].get("result")
                    if isinstance(step_results[step_id], dict) and "result" in step_results[step_id]
                    else step_results[step_id]
                )

        return {"workflow": workflow_name, "steps": step_results}

    async def run_action(
        self, domain: str, action_name: str,
        params: Dict[str, Any], run_by: str,
    ) -> Dict[str, Any]:
        """单动作执行（evals 与外部触发共用；返回状态供断言）"""
        action_type = await self.action_store.get_type_by_name(domain, action_name)
        if not action_type:
            raise ValueError(f"动作不存在: {domain}/{action_name}")

        idem = None
        if action_type.idempotency_key_template:
            # {name} 占位：params.name 优先（如模块名），否则回落动作名
            fmt_vars = {**{"name": action_type.name}, **params}
            try:
                idem = action_type.idempotency_key_template.format(**fmt_vars)
            except KeyError:
                idem = None

        exec = await self.sm.stage(
            action_type_id=action_type.id, params=params,
            staged_by=run_by, idempotency_key=idem,
        )
        return {"status": exec.status, "exec_id": exec.id}

    # ---------- 步骤实现 ----------

    async def _query_step(self, step: Dict[str, Any]) -> List[Dict[str, Any]]:
        obj_type = await self.object_store.get_type_by_name(
            step.get("domain") or self._current_domain, step["object_type"]
        )
        if not obj_type:
            raise ValueError(f"query_step 对象类型不存在: {step['object_type']}")
        objects = await self.object_store.list_objects(type_id=obj_type.id, limit=100)
        filters = step.get("filter") or {}
        return [
            {"id": o.id, "title": o.title, "properties": o.properties}
            for o in objects
            if all((o.properties or {}).get(k) == v for k, v in filters.items())
        ]

    async def _ai_step(self, step: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        prefix = (step.get("prompt_prefix") or "").strip()
        var_name = step.get("prompt_var")
        variable = context.get(var_name) if var_name else None
        if isinstance(variable, (list, dict)):
            variable = json.dumps(variable, ensure_ascii=False)

        prompt = f"{prefix}\n\n{variable}" if variable is not None else prefix
        content = await call_model(step.get("model", "deepseek-chat"), prompt)

        result: Any = content
        if step.get("expect_json"):
            result = self._parse_json_array(content)

        return {"content": content, "result": result}

    async def _action_step(self, step: Dict[str, Any], context: Dict[str, Any], run_by: str) -> Dict[str, Any]:
        action_name = step["action"]

        # 迭代展开：iterate_over 引用上游 JSON 数组输出，逐项执行
        iterate_over = step.get("iterate_over")
        if iterate_over:
            items = context.get(iterate_over) or []
            if not isinstance(items, list):
                raise ValueError(f"iterate_over 目标不是数组: {iterate_over}")
            statuses = []
            for item in items:
                context["$item"] = item
                statuses.append(await self._exec_one_action(action_name, step, context, run_by))
            context.pop("$item", None)
            staged = sum(1 for s in statuses if s["status"] == "staged")
            return {"statuses": statuses, "staged_count": staged}

        return await self._exec_one_action(action_name, step, context, run_by)

    async def _exec_one_action(self, action_name: str, step: Dict[str, Any],
                               context: Dict[str, Any], run_by: str) -> Dict[str, Any]:
        params = self._resolve_params(step.get("params") or {}, context)
        return await self.run_action(self._current_domain, action_name, params, run_by)

    # ---------- 辅助 ----------

    def _resolve_params(self, spec: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """$params.x / $output名 / $item.x 绑定解析"""
        resolved = {}
        for key, value in spec.items():
            if isinstance(value, str) and value.startswith("$"):
                path = value[1:]
                if path.startswith("params."):
                    resolved[key] = context["params"].get(path[len("params."):])
                elif path.startswith("item."):
                    item = context.get("$item") or {}
                    resolved[key] = item.get(path[len("item."):])
                else:
                    resolved[key] = context.get(path)
            else:
                resolved[key] = value
        return resolved

    @staticmethod
    def _parse_json_array(content: str) -> List[Dict[str, Any]]:
        """宽容解析：剥 markdown 代码栅栏、截取首个 JSON 数组"""
        text = content.strip()
        if text.startswith("```"):
            text = text.strip("`")
            if text.startswith("json"):
                text = text[4:]
        start = text.find("[")
        end = text.rfind("]")
        if start == -1 or end == -1 or end <= start:
            raise ValueError(f"AI 输出不含 JSON 数组: {content[:80]}")
        return json.loads(text[start:end + 1])

    async def _load_workflow(self, domain: str, name: str) -> Dict[str, Any]:
        from sqlalchemy import select
        result = await self.session.execute(
            select(Template).where(Template.domain == domain, Template.status == "published")
        )
        for tpl in result.scalars().all():
            for wf in tpl.workflows_json or []:
                if wf.get("name") == name:
                    self._current_domain = domain
                    return wf
        raise ValueError(f"工作流不存在: {domain}/{name}")
