"""动作类型存储：upsert + DSL 注册 + 查询"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Optional, Dict, Any, List

from yuanzhu.db.models import ActionType
from yuanzhu.models.action import ActionTypeCreate


class ActionStore:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_type(self, type_data: ActionTypeCreate) -> ActionType:
        existing = await self.get_type_by_name(type_data.domain, type_data.name)
        if existing:
            return await self._apply_fields(existing, type_data)

        action_type = ActionType(name="", domain="")  # 字段由 _apply_fields 填充
        await self._apply_fields(action_type, type_data)
        self.session.add(action_type)
        await self.session.flush()
        await self.session.refresh(action_type)
        return action_type

    async def register_from_dsl(self, parsed: Dict[str, Any]) -> ActionType:
        """parse_action_type_yaml 的产物注册（幂等 upsert）"""
        return await self.create_type(ActionTypeCreate(**parsed))

    async def _apply_fields(self, action_type: ActionType, data: ActionTypeCreate):
        action_type.name = data.name
        action_type.domain = data.domain
        action_type.params_schema_json = data.params_schema
        action_type.submission_criteria_json = data.submission_criteria
        action_type.transform_json = data.transform
        action_type.side_effects_json = data.side_effects
        action_type.autonomy_level = data.autonomy_level
        action_type.requires_staging = data.requires_staging
        action_type.description_for_agent = data.description_for_agent
        action_type.idempotency_key_template = data.idempotency_key_template
        await self.session.flush()
        return action_type

    async def get_type(self, type_id: int) -> Optional[ActionType]:
        return await self.session.get(ActionType, type_id)

    async def get_type_by_name(self, domain: str, name: str) -> Optional[ActionType]:
        result = await self.session.execute(
            select(ActionType).where(ActionType.domain == domain, ActionType.name == name)
        )
        return result.scalar_one_or_none()

    async def get_type_by_name_ci(self, domain: str, name: str) -> Optional[ActionType]:
        """大小写不敏感匹配（MCP 工具名 lower 后回查）"""
        result = await self.session.execute(
            select(ActionType).where(
                func.lower(ActionType.domain) == domain.lower(),
                func.lower(ActionType.name) == name.lower(),
            )
        )
        return result.scalar_one_or_none()

    async def list_types(self, domain: Optional[str] = None) -> List[ActionType]:
        query = select(ActionType)
        if domain:
            query = query.where(ActionType.domain == domain)
        result = await self.session.execute(query.order_by(ActionType.id))
        return list(result.scalars().all())
