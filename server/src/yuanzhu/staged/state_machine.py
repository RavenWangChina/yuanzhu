"""Staged writes 状态机（编排入口，spec 3.1 + ADR-006）

职责拆分（对抗审查修订：不再 God Object）：
- 本类：状态流转（staged→approved→applied / rejected / reverted）+ stage 入口编排
- SubmissionCriteriaValidator（criteria.py）：语义前置校验
- TransformEngine（transform.py）：确定性转换规则
- ActionExecutor / Compensator（executor.py）：执行与补偿

autonomy（ADR-006 读高写低）：
- L1 / requires_staging=False → stage 内自动 approve+apply（确定性动作）
- L2+（默认）→ staged 等人审；L3-L5 v0.1 统一按 L2 流程，字段先行
"""
import copy
from typing import Dict, Any, List, Optional

from sqlalchemy import select
from jsonschema import validate as schema_validate, ValidationError

from yuanzhu.db.models import ActionType, ActionExec, utcnow
from yuanzhu.ontology.object_store import ObjectStore
from yuanzhu.staged.criteria import validate_submission_criteria
from yuanzhu.staged.executor import ActionExecutor, Compensator

# 合法状态转换表
VALID_TRANSITIONS = {
    "staged": {"approved", "rejected"},
    "approved": {"applied", "rejected"},
    "applied": {"reverted"},
    "rejected": set(),
    "reverted": set(),
}


class StagedStateMachine:
    def __init__(self, session):
        self.session = session
        self.object_store = ObjectStore(session)
        self.executor = ActionExecutor(session)
        self.compensator = Compensator(session)

    # ---------- 入口 ----------

    async def stage(
        self,
        action_type_id: int,
        params: Dict[str, Any],
        staged_by: str,
        idempotency_key: Optional[str] = None,
    ) -> ActionExec:
        """stage 动作：校验（格式+语义）→ 幂等检查 → 建 staged 记录（含 before 快照）"""
        action_type = await self.session.get(ActionType, action_type_id)
        if not action_type:
            raise ValueError(f"动作类型不存在: {action_type_id}")

        # 1. JSON Schema 管格式
        try:
            schema_validate(instance=params, schema=action_type.params_schema_json or {})
        except ValidationError as e:
            raise ValueError(f"参数验证失败: {e.message}") from e

        # 2. submission_criteria 管语义（运行时状态校验）
        await validate_submission_criteria(
            action_type.submission_criteria_json, params, self.object_store
        )

        # 3. 幂等键：已有同键记录直接返回（重试返回缓存结果）
        if idempotency_key:
            existing = await self.session.execute(
                select(ActionExec).where(ActionExec.idempotency_key == idempotency_key)
            )
            found = existing.scalar_one_or_none()
            if found:
                return found

        # 4. before 快照（审批上下文：谁/为什么/影响哪些对象的原值）
        exec = ActionExec(
            action_type_id=action_type_id,
            params_json=params,
            idempotency_key=idempotency_key,
            status="staged",
            staged_by=staged_by,
            staged_at=utcnow(),
        )
        exec.exec_log_json = await self._snapshot_before(action_type, params)
        self.session.add(exec)
        await self.session.flush()
        await self.session.refresh(exec)

        # 5. autonomy 策略：L1/非 staged 动作自动执行
        if not action_type.requires_staging:
            exec.status = "approved"
            exec.reviewed_by = "system-autonomy-L1"
            exec.reviewed_at = utcnow()
            await self.session.flush()
            return await self.apply(exec.id, action_type=action_type)

        return exec

    # ---------- 审批 ----------

    async def approve(
        self, exec_id: int, reviewed_by: str, review_comment: Optional[str] = None
    ) -> ActionExec:
        exec = await self._get_exec(exec_id)
        self._transition(exec, "approved")
        exec.reviewed_by = reviewed_by
        exec.reviewed_at = utcnow()
        exec.review_comment = review_comment
        await self.session.flush()
        await self.session.refresh(exec)
        return exec

    async def reject(
        self, exec_id: int, reviewed_by: str, review_comment: str
    ) -> ActionExec:
        exec = await self._get_exec(exec_id)
        self._transition(exec, "rejected")
        exec.reviewed_by = reviewed_by
        exec.reviewed_at = utcnow()
        exec.review_comment = review_comment
        await self.session.flush()
        await self.session.refresh(exec)
        return exec

    async def apply(self, exec_id: int, action_type: Optional[ActionType] = None) -> ActionExec:
        """应用 approved 动作（transform 规则执行 + 副作用记录）"""
        exec = await self._get_exec(exec_id)
        self._transition(exec, "applied")
        if action_type is None:
            action_type = await self.session.get(ActionType, exec.action_type_id)
        exec = await self.executor.execute(exec, action_type)
        exec.status = "applied"
        await self.session.flush()
        await self.session.refresh(exec)
        return exec

    async def revert(self, exec_id: int) -> ActionExec:
        """补偿事务：恢复 before 快照（幂等）"""
        exec = await self._get_exec(exec_id)
        self._transition(exec, "reverted")
        exec = await self.compensator.compensate(exec)
        exec.status = "reverted"
        await self.session.flush()
        await self.session.refresh(exec)
        return exec

    # ---------- 查询 ----------

    async def list_pending(self, domain: Optional[str] = None) -> List[ActionExec]:
        query = (
            select(ActionExec)
            .where(ActionExec.status == "staged")
            .order_by(ActionExec.staged_at)
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    # ---------- 内部 ----------

    async def _snapshot_before(
        self, action_type: ActionType, params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """目标对象原值快照（transform 涉及对象时）"""
        if not action_type.transform_json:
            return {}
        object_id = params.get("object_id")
        if object_id is None:
            return {}
        obj = await self.object_store.get_object(int(object_id))
        if not obj:
            raise ValueError(f"目标对象不存在: {object_id}")
        return {"before": copy.deepcopy(obj.properties_json or {})}

    def _transition(self, exec: ActionExec, new_status: str) -> None:
        allowed = VALID_TRANSITIONS.get(exec.status, set())
        if new_status not in allowed:
            raise ValueError(
                f"非法状态转换: {exec.status} → {new_status}"
                f"（{exec.status} 只能转为 {sorted(allowed) or ['（终态）']}）"
            )
        exec.status = new_status

    async def _get_exec(self, exec_id: int) -> ActionExec:
        exec = await self.session.get(ActionExec, exec_id)
        if not exec:
            raise ValueError(f"动作执行记录不存在: {exec_id}")
        return exec
