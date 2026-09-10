"""ActionExecutor / Compensator：动作的执行与补偿（副作用可中和）

执行 = before 快照 + transform 规则应用 + 对象更新。
补偿 = 用 before 快照恢复对象属性（幂等：恢复到快照值本身幂等）。

side_effects（v0.1 边界）：仅记录到 exec_log（webhook/notify 实现留里程碑 3+）。
"""
import copy
from typing import Any, Dict, Optional

from yuanzhu.db.models import ActionType, ActionExec
from yuanzhu.ontology.object_store import ObjectStore
from yuanzhu.staged.transform import apply_transform
from yuanzhu.db.models import utcnow


class ActionExecutor:
    """应用 approved 动作（transform 规则引擎驱动）"""

    def __init__(self, session):
        self.session = session
        self.object_store = ObjectStore(session)

    async def execute(self, exec: ActionExec, action_type: ActionType) -> ActionExec:
        params: Dict[str, Any] = exec.params_json or {}

        # 目标对象：取 params 中的 object_id（若动作声明了 transform）
        object_id = params.get("object_id")
        transform_log = []

        if action_type.transform_json and object_id is not None:
            obj = await self.object_store.get_object(int(object_id))
            if not obj:
                raise ValueError(f"目标对象不存在: {object_id}")

            # before 快照（审批上下文 + 补偿依据）
            before = copy.deepcopy(obj.properties_json or {})
            log = exec.exec_log_json or {}
            log["before"] = before

            new_props = apply_transform(action_type.transform_json, params, obj.properties_json or {})
            obj.properties_json = new_props
            await self.session.flush()

            transform_log = [
                {"object_id": obj.id,
                 "set": rule.get("set"),
                 "to": (new_props.get(rule["set"][len("properties."):])
                        if rule.get("set", "").startswith("properties.") else None)}
                for rule in action_type.transform_json
            ]
            log["transform_log"] = transform_log
            exec.exec_log_json = log

        # side_effects：v0.1 仅记录（webhook/notify 执行留里程碑 3+）
        if action_type.side_effects_json:
            log = exec.exec_log_json or {}
            log["side_effects_deferred"] = action_type.side_effects_json
            exec.exec_log_json = log

        exec.applied_at = utcnow()
        await self.session.flush()
        return exec


class Compensator:
    """补偿事务：用 before 快照恢复（语义反操作，幂等）"""

    def __init__(self, session):
        self.session = session
        self.object_store = ObjectStore(session)

    async def compensate(self, exec: ActionExec) -> ActionExec:
        params: Dict[str, Any] = exec.params_json or {}
        object_id = params.get("object_id")
        log = exec.exec_log_json or {}

        if object_id is not None and "before" in log:
            obj = await self.object_store.get_object(int(object_id))
            if obj:
                obj.properties_json = copy.deepcopy(log["before"])
                await self.session.flush()

        exec.reverted_at = utcnow()
        await self.session.flush()
        return exec
