"""评测集执行器：模板自带用例的运行与断言（四段式之④=硬化清单 evals 项）

用例结构（evals/cases.yaml）：
    cases:
      - name: ...
        steps:
          - action: X           # 执行动作（经 WorkflowEngine.run_action）
            params: {...}       # 支持 $last_<type> 引用最近创建的对象
            expect: {status: staged}   # 步内断言（可选）
          - approve: {}         # 审批通过（approve+apply）
        expect:                 # 用例级断言
          status: applied       # 最后动作状态
          object_exists: {type: T, name|title: v}   # 对象入库验证
          error_contains: submission_criteria        # 期望报错包含
"""
from typing import Any, Dict, List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from yuanzhu.db.models import Template
from yuanzhu.workflow.engine import WorkflowEngine
from yuanzhu.ontology.object_store import ObjectStore
from yuanzhu.staged.state_machine import StagedStateMachine


class EvalsRunner:
    def __init__(self, session: AsyncSession):
        import uuid
        self._run_id = uuid.uuid4().hex[:8]   # C1：本次评测运行标识
        self.session = session
        self.engine = WorkflowEngine(session)
        self.object_store = ObjectStore(session)
        self.sm = StagedStateMachine(session)

    async def run_template(self, domain: str, status: str = "published") -> Dict[str, Any]:
        """跑某域模板的评测用例（status 可选 draft——forge 守门场景）"""
        result = await self.session.execute(
            select(Template).where(Template.domain == domain, Template.status == status)
        )
        cases: List[Dict[str, Any]] = []
        for tpl in result.scalars().all():
            for case in tpl.evals_json or []:
                case["_domain"] = domain   # 跨域：动作按所属域解析
                cases.append(case)

        results = []
        shared_context: Dict[str, Any] = {}  # 跨用例共享（用例链：建对象→引用）
        for case in cases:
            try:
                ok, detail = await self._run_case(case, shared_context)
                results.append({"name": case["name"], "ok": ok, "detail": detail})
            except Exception as e:
                results.append({"name": case["name"], "ok": False, "detail": str(e)})

        passed = sum(1 for r in results if r["ok"])
        report = {
            "domain": domain,
            "total": len(results),
            "passed": passed,
            "failed": len(results) - passed,
            "cases": results,
        }
        await self._cleanup_test_objects()
        return report

    async def _cleanup_test_objects(self) -> int:
        """评测副作用清理：删掉 eval- 前缀参数创建的对象（exec 审计记录保留）。

        误删防护：只删 params 里 title/question/takeaway 以 eval- 开头的 applied exec
        所创建的对象（created_object_ids），不按库内值模糊匹配。
        """
        from sqlalchemy import select as _sel
        from yuanzhu.db.models import ActionExec
        execs = (await self.session.execute(
            _sel(ActionExec).where(ActionExec.status == "applied"))).scalars().all()
        removed = 0
        for e in execs:
            params = e.params_json or {}
            key = next((k for k in ("title", "question", "takeaway") if k in params), None)
            if key and str(params[key]).startswith("eval-"):
                for oid in (e.exec_log_json or {}).get("created_object_ids", []):
                    if await self.object_store.delete_object(oid):
                        removed += 1
        if removed:
            await self.session.flush()
        return removed

    # ---------- 单用例 ----------

    async def _run_case(self, case: Dict[str, Any], context: Dict[str, Any]):
        """执行一个用例（context 跨用例共享：$last_<type> 引用链）；expect 断言收尾"""
        last_result: Dict[str, Any] = {}
        last_error: str = ""
        last_action_name = ""

        for step in case.get("steps", []):
            if "action" in step:
                params = self._resolve_refs(step.get("params") or {}, context)
                last_action_name = step["action"]
                try:
                    # C1 修复：evals 路径幂等键追加 run 标识——避免与真实执行
                    # （及历史 evals 记录）互相占用幂等键导致第二次跑必挂
                    idem_suffix = f"#evals-{self._run_id}"
                    last_result = await self.engine.run_action(
                        domain=case.get("_domain", "aiqa"),
                        action_name=step["action"],
                        params=params,
                        run_by="evals-runner",
                        idempotency_suffix=idem_suffix,
                    )
                    last_error = ""
                    # applied（L1）时立刻可拿到 created_object_ids
                    exec = await self.session.get(
                        __import__("yuanzhu.db.models", fromlist=["ActionExec"]).ActionExec,
                        last_result.get("exec_id"),
                    )
                    if exec and exec.status == "applied":
                        self._register_created(last_action_name, exec, context)
                except ValueError as e:
                    last_error = str(e)
                    last_result = {"error": str(e)}

                # 步内断言
                step_expect = step.get("expect")
                if step_expect and "status" in step_expect:
                    if last_result.get("status") != step_expect["status"]:
                        return False, (
                            f"步骤 {step['action']} 状态 {last_result.get('status')}"
                            f" ≠ 期望 {step_expect['status']}"
                        )

            elif "approve" in step:
                exec_id = last_result.get("exec_id")
                if not exec_id:
                    return False, "approve 前无 staged 动作"
                await self.sm.approve(exec_id, reviewed_by="evals-runner")
                applied = await self.sm.apply(exec_id)
                last_result = {"status": applied.status, "exec_id": exec_id}
                # approve 后 created_object_ids 才落 exec_log——此处补注册
                self._register_created(last_action_name, applied, context)

        return await self._assert_expect(
            case.get("expect") or {}, last_result, last_error, context,
            current_domain=case.get("_domain", "aiqa"))

    async def _assert_expect(self, expect: Dict[str, Any], last_result, last_error, context,
                             current_domain: str = "aiqa"):
        if "error_contains" in expect:
            if expect["error_contains"] not in last_error:
                return False, f"期望报错含 {expect['error_contains']!r}，实际: {last_error!r}"
            return True, "语义拦截符合预期"

        if "status" in expect:
            if last_result.get("status") != expect["status"]:
                return False, f"终态 {last_result.get('status')} ≠ 期望 {expect['status']}"

        if "object_exists" in expect:
            found = await self._object_exists(
                expect["object_exists"], domain=current_domain)
            if not found:
                return False, f"对象未入库: {expect['object_exists']}"
        return True, "通过"

    # ---------- 辅助 ----------

    def _resolve_refs(self, params: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """$last_bug → 最近创建的 Bug 对象 id"""
        resolved = {}
        for k, v in params.items():
            if isinstance(v, str) and v.startswith("$last_"):
                resolved[k] = context.get(v)  # context 键带 $ 前缀
            else:
                resolved[k] = v
        return resolved

    def _register_created(self, action_name: str, exec, context: Dict[str, Any]):
        """记 $last_<type> = 最近该类型创建的对象 id（来自 exec_log.created_object_ids）"""
        if not action_name:
            return
        lower = action_name.lower()
        for prefix in ("create", "register"):
            if lower.startswith(prefix):
                ids = (exec.exec_log_json or {}).get("created_object_ids") or []
                if ids:
                    context["$last_" + lower[len(prefix):]] = ids[0]
                break

    async def _object_exists(self, spec: Dict[str, Any], domain: str = "aiqa") -> bool:
        obj_type = await self.object_store.get_type_by_name(domain, spec["type"])
        if not obj_type:
            return False
        objects = await self.object_store.list_objects(type_id=obj_type.id, limit=200)
        for key, value in spec.items():
            if key == "type":
                continue
            return any((o.properties or {}).get(key) == value for o in objects)
        return len(objects) > 0
