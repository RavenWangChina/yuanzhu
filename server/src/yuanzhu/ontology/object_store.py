"""对象存储层：类型 CRUD（upsert）+ 实例 CRUD + schema 校验"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional, Dict, Any

from jsonschema import validate, ValidationError

from yuanzhu.db.models import ObjectType, Object
from yuanzhu.models.object import ObjectTypeCreate, ObjectCreate, ObjectUpdate


def _build_schema(properties: Dict[str, Any]) -> Dict[str, Any]:
    """properties 简写 DSL → JSON Schema（与 schema.py 保持一致）"""
    schema: Dict[str, Any] = {"type": "object", "properties": {}, "required": []}
    for prop_name, prop_def in properties.items():
        prop_json: Dict[str, Any] = {"type": prop_def.get("type", "string")}
        for key in ("enum", "default", "minimum", "maximum", "description"):
            if key in prop_def:
                prop_json[key] = prop_def[key]
        schema["properties"][prop_name] = prop_json
        if prop_def.get("required", False):
            schema["required"].append(prop_name)
    return schema


class ObjectStore:
    def __init__(self, session: AsyncSession):
        self.session = session

    # ---------- 类型 ----------

    async def create_type(self, type_data: ObjectTypeCreate) -> ObjectType:
        """创建或更新对象类型（domain+name 幂等 upsert，模板注册复用）"""
        existing = await self.get_type_by_name(type_data.domain, type_data.name)
        if existing:
            existing.title_key = type_data.title_key
            existing.description = type_data.description
            existing.schema_json = _build_schema(type_data.properties)
            existing.exposed = type_data.exposed
            await self.session.flush()
            return existing

        obj_type = ObjectType(
            name=type_data.name,
            domain=type_data.domain,
            title_key=type_data.title_key,
            description=type_data.description,
            schema_json=_build_schema(type_data.properties),
            exposed=type_data.exposed,
        )
        self.session.add(obj_type)
        await self.session.flush()
        await self.session.refresh(obj_type)
        return obj_type

    async def get_type(self, type_id: int) -> Optional[ObjectType]:
        return await self.session.get(ObjectType, type_id)

    async def get_type_by_name(self, domain: str, name: str) -> Optional[ObjectType]:
        result = await self.session.execute(
            select(ObjectType).where(ObjectType.domain == domain, ObjectType.name == name)
        )
        return result.scalar_one_or_none()

    async def list_types(self, domain: Optional[str] = None) -> List[ObjectType]:
        query = select(ObjectType)
        if domain:
            query = query.where(ObjectType.domain == domain)
        result = await self.session.execute(query.order_by(ObjectType.id))
        return list(result.scalars().all())

    # ---------- 实例 ----------

    async def create_object(self, obj_data: ObjectCreate) -> Object:
        obj_type = await self.get_type(obj_data.type_id)
        if not obj_type:
            raise ValueError(f"对象类型不存在: {obj_data.type_id}")

        self._validate_properties(obj_type, obj_data.properties)

        title = obj_data.title
        if not title and obj_type.title_key:
            title = obj_data.properties.get(obj_type.title_key)

        obj = Object(
            type_id=obj_data.type_id,
            properties_json=obj_data.properties,
            title=title,
            created_by=obj_data.created_by,
        )
        self.session.add(obj)
        await self.session.flush()
        await self.session.refresh(obj)
        return obj

    async def get_object(self, obj_id: int) -> Optional[Object]:
        result = await self.session.execute(select(Object).where(Object.id == obj_id))
        obj = result.scalar_one_or_none()
        return obj

    async def list_objects(
        self,
        type_id: Optional[int] = None,
        domain: Optional[str] = None,
        created_by: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Object]:
        query = select(Object)
        if type_id:
            query = query.where(Object.type_id == type_id)
        if created_by:
            query = query.where(Object.created_by == created_by)
        if domain:
            query = query.join(ObjectType).where(ObjectType.domain == domain)

        query = query.order_by(Object.created_at.desc()).limit(limit).offset(offset)
        result = await self.session.execute(query)
        return list(result.scalars().unique().all())

    async def update_object(self, obj_id: int, update_data: ObjectUpdate) -> Object:
        obj = await self.get_object(obj_id)
        if not obj:
            raise ValueError(f"对象不存在: {obj_id}")

        if update_data.properties:
            new_properties = {**(obj.properties_json or {}), **update_data.properties}
            obj_type = await self.get_type(obj.type_id)
            self._validate_properties(obj_type, new_properties)
            obj.properties_json = new_properties

        obj_type = await self.get_type(obj.type_id)
        if update_data.title:
            obj.title = update_data.title
        elif obj_type and obj_type.title_key:
            obj.title = (obj.properties_json or {}).get(obj_type.title_key)

        await self.session.flush()
        await self.session.refresh(obj)
        return obj

    async def delete_object(self, obj_id: int) -> bool:
        obj = await self.get_object(obj_id)
        if not obj:
            return False
        await self.session.delete(obj)
        await self.session.flush()
        return True

    # ---------- 校验 ----------

    @staticmethod
    def _validate_properties(obj_type: ObjectType, properties: Dict[str, Any]):
        """JSON Schema 管格式（约束解码），submission_criteria 管语义（DMLA 分层）"""
        try:
            validate(instance=properties, schema=obj_type.schema_json)
        except ValidationError as e:
            raise ValueError(f"属性验证失败: {e.message}") from e
