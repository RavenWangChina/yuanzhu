"""工作流执行引擎（spec 3.2：steps = action_step | ai_step | query_step）

- ai_step 提示词分区（ADR-008）：稳定前缀（模板内 prompt_prefix，缓存友好）
  + 可变段（prompt_var 绑定的运行时数据），只发可变段给模型、前缀由引擎拼接
- action_step 走 staged 状态机（写低；L1 自动、L2+ 人审）
- query_step 查本体对象（读高）
- 变量绑定：$params.x（入参）/ $output（上游步骤输出）/ $item.x（迭代项）
"""
import json
from typing import Any, Dict, List, Optional, Callable

from sqlalchemy.ext.asyncio import AsyncSession

from yuanzhu.db.models import Template
from yuanzhu.staged.state_machine import StagedStateMachine
from yuanzhu.ontology.object_store import ObjectStore
from yuanzhu.ontology.action_store import ActionStore


async def call_model(model: str, prompt: str, session=None, caller: str = "ai-step") -> str:
    """ai_step 的模型调用（经网关；测试被 monkeypatch 替换）

    失败转 ValueError（携带模型名上下文）——不带上下文的兜底=二次浪费（DMLA）。
    I4 修复：session 提供时提取 usage 落 ModelUsage（成本计量不再绕过）。
    """
    from yuanzhu.gateway.proxy import acompletion
    try:
        response = await acompletion(
            model=model,
            messages=[{"role": "user", "content": prompt}],
        )
    except Exception as e:
        raise ValueError(f"AI 步骤模型调用失败（model={model}）: {e}") from e
    data = response if isinstance(response, dict) else response.model_dump()

    if session is not None:
        try:
            from yuanzhu.gateway.proxy import extract_usage, build_usage_record
            usage = extract_usage(response)
            session.add(build_usage_record(
                model=model, usage=usage, task_id=None, caller=caller))
        except Exception:
            pass  # 计量失败不阻断主流程（usage 缺失时记 0）

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
        on_step: Optional[Callable] = None,
    ) -> Dict[str, Any]:
        """执行工作流（顺序步骤 + parallel 并行组；v0.1.4：on_step(step_id) 步骤完成回调）"""
        workflow = await self._load_workflow(domain, workflow_name)

        context: Dict[str, Any] = {"params": params}
        step_results: Dict[str, Any] = {}

        for step in workflow.get("steps", []):
            step_id = step.get("id")
            step_type = step.get("type")

            if step_type == "query_step":
                step_results[step_id] = await self._query_step(step)

            elif step_type == "ai_step":
                step_results[step_id] = await self._ai_step(step, context)

            elif step_type == "action_step":
                step_results[step_id] = await self._action_step(step, context, run_by)

            elif step_type == "parallel" or "parallel" in step:
                # T5 并行组：组内 asyncio.gather 并发（ai_step 用独立 session 计量——
                # AsyncSession 非并发安全，主 session 不进组）
                import asyncio as _aio
                from yuanzhu.db.database import async_session_factory as _sf

                async def _run_one(sub):
                    sub_id = sub["id"]
                    try:
                        if sub.get("type") == "ai_step":
                            async with _sf() as _ses:
                                return sub_id, await self._ai_step(sub, context, _ses)
                        elif sub.get("type") == "query_step":
                            return sub_id, await self._query_step(sub)
                        raise ValueError(
                            f"并行组暂不支持 {sub.get(chr(116)+chr(121)+chr(112)+chr(101))}"
                            "（v0.1.1 支持 ai/query）")
                    except Exception as e:
                        raise ValueError(f"并行步骤 [{sub_id}] 失败: {e}") from e

                results = await _aio.gather(*[_run_one(s) for s in step["parallel"]])
                for sub_id, res in results:
                    step_results[sub_id] = res

            else:
                raise ValueError(f"未知步骤类型: {step_type}（支持 action/ai/query/parallel）")

            if on_step and step_id:
                try:
                    on_step(step_id)
                except Exception:
                    pass   # 进度回调失败不影响主流程

            # 输出绑定（普通步骤绑自己的 output；并行组子步骤在组内绑）
            if step.get("output") and step_id in step_results:
                context[step["output"]] = (
                    step_results[step_id].get("result")
                    if isinstance(step_results[step_id], dict) and "result" in step_results[step_id]
                    else step_results[step_id]
                )

            if "parallel" in step:  # 子步骤 output 绑定进 context
                for sub in step["parallel"]:
                    if sub.get("output") and sub["id"] in step_results:
                        r = step_results[sub["id"]]
                        context[sub["output"]] = (
                            r.get("result") if isinstance(r, dict) and "result" in r else r)

        return {"workflow": workflow_name, "steps": step_results}

    async def run_action(
        self, domain: str, action_name: str,
        params: Dict[str, Any], run_by: str, idempotency_suffix: str = "",
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
                if idempotency_suffix:
                    idem += idempotency_suffix   # C1：evals 运行隔离
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

    async def _ai_step(self, step: Dict[str, Any], context: Dict[str, Any], session=None) -> Dict[str, Any]:
        prefix = (step.get("prompt_prefix") or "").strip()
        # 单上游（prompt_var）或多上游（prompt_vars，带标注块拼接——视角对抗/综合裁决）
        var_names = step.get("prompt_vars") or ([step["prompt_var"]] if step.get("prompt_var") else [])
        parts = []
        for name in var_names:
            v = context.get(name)
            if v is None:
                continue
            if isinstance(v, (list, dict)):
                v = json.dumps(v, ensure_ascii=False)
            if len(var_names) > 1:
                parts.append(f"【{name}】\n{v}")
            else:
                parts.append(str(v))
        variable = "\n\n".join(parts) if parts else None

        prompt = f"{prefix}\n\n{variable}" if variable is not None else prefix
        content = await call_model(step.get("model", "glm-5.1"), prompt,
                                   session=session or self.session, caller="ai-step")

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
