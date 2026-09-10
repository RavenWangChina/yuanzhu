"""MCP 工具生成器：本体 → agent 工具（spec 3.1，参考 ObjectStack exposed 标记）

- exposed=true 的对象类型 → query_{domain}_{name} 查询工具
- 动作类型 → execute_{domain}_{name} 执行工具（requires_staging 在描述中标注）
- 审批三件：list_pending_approvals / approve_action / reject_action
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Dict, Any, Optional

from yuanzhu.db.models import ObjectType, ActionType


APPROVAL_TOOLS: List[Dict[str, Any]] = [
    {
        "name": "list_pending_approvals",
        "description": "列出待审批的 staged 动作（含参数、暂存者、before 快照）",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "approve_action",
        "description": "批准 staged 动作（批准即应用 transform）",
        "inputSchema": {
            "type": "object",
            "properties": {
                "exec_id": {"type": "integer", "description": "动作执行 ID"},
                "comment": {"type": "string", "description": "审批意见"},
            },
            "required": ["exec_id"],
        },
    },
    {
        "name": "reject_action",
        "description": "拒绝 staged 动作（必须附拒绝理由）",
        "inputSchema": {
            "type": "object",
            "properties": {
                "exec_id": {"type": "integer", "description": "动作执行 ID"},
                "comment": {"type": "string", "description": "拒绝理由（必填）"},
            },
            "required": ["exec_id", "comment"],
        },
    },
]


class MCPToolGenerator:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def generate_query_tool(self, object_type_id: int) -> Optional[Dict[str, Any]]:
        obj_type = await self.session.get(ObjectType, object_type_id)
        if not obj_type or not obj_type.exposed:
            return None
        return {
            "name": f"query_{obj_type.domain}_{obj_type.name}".lower(),
            "description": f"查询 {obj_type.name} 对象。{obj_type.description or ''}".strip(),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "filter": {
                        "type": "object",
                        "description": "属性过滤条件（如 {\"status\": \"Open\"}）",
                    },
                    "limit": {"type": "integer", "description": "返回数量上限", "default": 10},
                },
            },
        }

    async def generate_action_tool(self, action_type_id: int) -> Optional[Dict[str, Any]]:
        action_type = await self.session.get(ActionType, action_type_id)
        if not action_type:
            return None
        description = action_type.description_for_agent or f"执行 {action_type.name} 动作"
        if action_type.requires_staging:
            description += "（需要审批）"
        return {
            "name": f"execute_{action_type.domain}_{action_type.name}".lower(),
            "description": description,
            "inputSchema": action_type.params_schema_json or {"type": "object"},
        }

    async def list_tools(self) -> List[Dict[str, Any]]:
        tools: List[Dict[str, Any]] = []

        result = await self.session.execute(
            select(ObjectType).where(ObjectType.exposed == True)  # noqa: E712
        )
        for obj_type in result.scalars().all():
            tool = await self.generate_query_tool(obj_type.id)
            if tool:
                tools.append(tool)

        result = await self.session.execute(select(ActionType))
        for action_type in result.scalars().all():
            tool = await self.generate_action_tool(action_type.id)
            if tool:
                tools.append(tool)

        tools.extend(APPROVAL_TOOLS)
        return tools
