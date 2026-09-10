"""ActionExecutor / Compensator：动作的执行与补偿（副作用可中和）

两类 transform 规则（数据驱动，无硬编码动作名）：
- set：改现有对象属性 [{"set": "properties.x", "from": "params.y" | "value": v}]
- create_object：建对象 [{"create_object": {"type": T}, "with": {k: "from:params.x"|"literal:v"}}]

补偿：
- set 类：before 快照恢复
- create_object 类：删除已建对象（created_object_ids）

side_effects（v0.1 边界）：仅记录到 exec_log（webhook/notify 实现留里程碑 3+）。
"""
import copy
from typing import Any, Dict

from yuanzhu.db.models import ActionType, ActionExec, utcnow
from yuanzhu.ontology.object_store import ObjectStore
from yuanzhu.staged.transform import apply_transform, resolve_with_value
from yuanzhu.models.object import ObjectCreate


class ActionExecutor:
    """应用 approved 动作（transform 规则引擎驱动）"""

    def __init__(self, session):
        self.session = session
        self.object_store = ObjectStore(session)

    async def execute(self, exec: ActionExec, action_type: ActionType) -> ActionExec:
        params: Dict[str, Any] = exec.params_json or {}
        log = exec.exec_log_json or {}
        object_id = params.get("object_id")
        transform_log = []

        rules = action_type.transform_json or []
        created_ids = []

        for rule in rules:
            if "create_object" in rule:
                obj = await self._create_object(rule, params, exec, action_type)
                created_ids.append(obj.id)
                transform_log.append({"created_object": obj.id, "type": rule["create_object"].get("type")})
            elif "set" in rule and object_id is not None:
                if "before" not in log:
                    obj = await self.object_store.get_object(int(object_id))
                    if not obj:
                        raise ValueError(f"目标对象不存在: {object_id}")
                    log["before"] = copy.deepcopy(obj.properties_json or {})
                new_props = apply_transform([rule], params, log["before"])
                obj = await self.object_store.get_object(int(object_id))
                obj.properties_json = new_props
                await self.session.flush()
                transform_log.append({"set": rule.get("set")})

        if created_ids:
            log["created_object_ids"] = created_ids
        if transform_log:
            log["transform_log"] = transform_log
        if action_type.side_effects_json:
            log["side_effects_deferred"] = action_type.side_effects_json
        if log:
            exec.exec_log_json = log

        exec.applied_at = utcnow()
        await self.session.flush()
        return exec

    async def _create_object(self, rule, params, exec: ActionExec, action_type: ActionType):
        """按 create_object 规则建对象；with 值支持 from:/literal: 前缀"""
        type_spec = rule.get("create_object") or {}
        domain = type_spec.get("domain") or action_type.domain
        type_name = type_spec.get("type")
        obj_type = await ObjectStore(self.session).get_type_by_name(domain, type_name)
        if not obj_type:
            raise ValueError(f"create_object 类型不存在: {domain}/{type_name}")

        properties = {}
        for key, spec in (rule.get("with") or {}).items():
            properties[key] = resolve_with_value(spec, params)

        return await self.object_store.create_object(ObjectCreate(
            type_id=obj_type.id,
            properties=properties,
            created_by=exec.staged_by,
        ))


class Compensator:
    """补偿事务：before 快照恢复 + 建对象删除（语义反操作，幂等）"""

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

        for created_id in log.get("created_object_ids", []):
            await self.object_store.delete_object(created_id)

        exec.reverted_at = utcnow()
        await self.session.flush()
        return exec
