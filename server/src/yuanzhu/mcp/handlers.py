"""MCP 请求处理器：tools/call 的业务分发"""
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Any, Dict

from yuanzhu.ontology.object_store import ObjectStore
from yuanzhu.ontology.action_store import ActionStore
from yuanzhu.staged.state_machine import StagedStateMachine


def _parse_tool_name(tool_name: str, prefix: str):
    """execute_test_changepriority → ('test', 'changepriority')；解析失败返回 None"""
    if not tool_name.startswith(prefix):
        return None
    rest = tool_name[len(prefix):]
    parts = rest.split("_", 1)
    if len(parts) != 2:
        return None
    return parts[0], parts[1]


class MCPHandlers:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.object_store = ObjectStore(session)
        self.action_store = ActionStore(session)
        self.state_machine = StagedStateMachine(session)

    async def handle_query(self, tool_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        parsed = _parse_tool_name(tool_name, "query_")
        if not parsed:
            return {"error": f"无效的查询工具名: {tool_name}"}
        domain, type_name = parsed

        obj_type = await self.object_store.get_type_by_name_ci(domain, type_name)
        if not obj_type:
            return {"error": f"对象类型不存在: {domain}/{type_name}"}
        limit = min(int(params.get("limit", 10) or 10), 200)  # I5：DoS 面钳制
        objects = await self.object_store.list_objects(type_id=obj_type.id, limit=limit)

        filters = params.get("filter") or {}
        matched = [
            obj for obj in objects
            if all((obj.properties or {}).get(k) == v for k, v in filters.items())
        ]
        return {
            "objects": [
                {"id": o.id, "title": o.title, "properties": o.properties}
                for o in matched
            ]
        }

    async def handle_execute(self, tool_name: str, params: Dict[str, Any], agent_id: str) -> Dict[str, Any]:
        parsed = _parse_tool_name(tool_name, "execute_")
        if not parsed:
            return {"error": f"无效的动作工具名: {tool_name}"}
        domain, action_name = parsed

        action_type = await self.action_store.get_type_by_name_ci(domain, action_name)
        if not action_type:
            return {"error": f"动作类型不存在: {domain}/{action_name}"}

        idempotency_key = None
        if action_type.idempotency_key_template:
            try:
                idempotency_key = action_type.idempotency_key_template.format(
                    **params, name=action_type.name
                )
            except KeyError:
                idempotency_key = None  # 模板引用的参数缺失，退化为无幂等键

        try:
            exec = await self.state_machine.stage(
                action_type_id=action_type.id,
                params=params,
                staged_by=agent_id,
                idempotency_key=idempotency_key,
            )
        except ValueError as e:
            return {"error": str(e)}

        if exec.status == "applied":
            return {"exec_id": exec.id, "status": "applied", "message": "动作已自动执行（L1 自主性）"}

        return {
            "exec_id": exec.id,
            "status": exec.status,
            "message": "动作已暂存，等待人审（可在待审中心或用 approve_action 处理）",
            "before": (exec.exec_log_json or {}).get("before"),
        }

    async def handle_list_pending(self, params: Dict[str, Any]) -> Dict[str, Any]:
        pending = await self.state_machine.list_pending()
        items = []
        for exec in pending:
            action_type = await self.action_store.get_type(exec.action_type_id)
            items.append({
                "exec_id": exec.id,
                "action": f"{action_type.domain}/{action_type.name}" if action_type else "?",
                "params": exec.params_json,
                "staged_by": exec.staged_by,
                "staged_at": exec.staged_at.isoformat() if exec.staged_at else None,
                "before": (exec.exec_log_json or {}).get("before"),
            })
        return {"pending": items}

    async def handle_approve(self, params: Dict[str, Any], reviewer_id: str) -> Dict[str, Any]:
        exec_id = params.get("exec_id")
        if not exec_id:
            return {"error": "缺少 exec_id"}
        try:
            await self.state_machine.approve(
                exec_id, reviewed_by=reviewer_id, review_comment=params.get("comment")
            )
            exec = await self.state_machine.apply(exec_id)
            return {"exec_id": exec.id, "status": exec.status, "message": "已批准并应用"}
        except ValueError as e:
            return {"error": str(e)}

    async def handle_reject(self, params: Dict[str, Any], reviewer_id: str) -> Dict[str, Any]:
        exec_id = params.get("exec_id")
        comment = params.get("comment")
        if not exec_id:
            return {"error": "缺少 exec_id"}
        if not comment:
            return {"error": "缺少拒绝理由 comment"}
        try:
            exec = await self.state_machine.reject(exec_id, reviewed_by=reviewer_id, review_comment=comment)
            return {"exec_id": exec.id, "status": exec.status, "message": "已拒绝"}
        except ValueError as e:
            return {"error": str(e)}
