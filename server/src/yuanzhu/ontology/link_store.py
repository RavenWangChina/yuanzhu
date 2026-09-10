"""链接存储层：类型（upsert + 按名注册）+ 实例（cardinality 约束）"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional

from yuanzhu.db.models import LinkType, Link
from yuanzhu.models.link import LinkTypeCreate, LinkCreate


class LinkStore:
    def __init__(self, session: AsyncSession):
        self.session = session

    # ---------- 类型 ----------

    async def create_type(self, type_data: LinkTypeCreate) -> LinkType:
        """创建或更新链接类型（domain+name 幂等 upsert）"""
        existing = await self.get_type_by_name(type_data.domain, type_data.name)
        if existing:
            existing.source_type_id = type_data.source_type_id
            existing.target_type_id = type_data.target_type_id
            existing.cardinality = type_data.cardinality
            await self.session.flush()
            return existing

        link_type = LinkType(
            name=type_data.name,
            domain=type_data.domain,
            source_type_id=type_data.source_type_id,
            target_type_id=type_data.target_type_id,
            cardinality=type_data.cardinality,
        )
        self.session.add(link_type)
        await self.session.flush()
        await self.session.refresh(link_type)
        return link_type

    async def register_type_by_name(
        self, domain: str, name: str, source_type: str, target_type: str,
        cardinality: str = "many",
    ) -> LinkType:
        """DSL 按类型名注册（parse_link_type_yaml 的产物在此解析为 type_id）"""
        from yuanzhu.ontology.object_store import ObjectStore
        obj_store = ObjectStore(self.session)

        source = await obj_store.get_type_by_name(domain, source_type)
        if not source:
            raise ValueError(f"源对象类型不存在: {domain}/{source_type}")
        target = await obj_store.get_type_by_name(domain, target_type)
        if not target:
            raise ValueError(f"目标对象类型不存在: {domain}/{target_type}")

        return await self.create_type(LinkTypeCreate(
            name=name, domain=domain,
            source_type_id=source.id, target_type_id=target.id,
            cardinality=cardinality,
        ))

    async def get_type(self, type_id: int) -> Optional[LinkType]:
        return await self.session.get(LinkType, type_id)

    async def get_type_by_name(self, domain: str, name: str) -> Optional[LinkType]:
        result = await self.session.execute(
            select(LinkType).where(LinkType.domain == domain, LinkType.name == name)
        )
        return result.scalar_one_or_none()

    async def list_types(self, domain: Optional[str] = None) -> List[LinkType]:
        query = select(LinkType)
        if domain:
            query = query.where(LinkType.domain == domain)
        result = await self.session.execute(query.order_by(LinkType.id))
        return list(result.scalars().all())

    # ---------- 实例 ----------

    async def create_link(self, link_data: LinkCreate) -> Link:
        link_type = await self.get_type(link_data.type_id)
        if not link_type:
            raise ValueError(f"链接类型不存在: {link_data.type_id}")

        if link_type.cardinality == "one":
            existing = await self.session.execute(
                select(Link).where(
                    Link.type_id == link_data.type_id,
                    Link.source_id == link_data.source_id,
                )
            )
            if existing.scalar_one_or_none():
                raise ValueError("链接已存在（one-to-one 约束）")

        link = Link(
            type_id=link_data.type_id,
            source_id=link_data.source_id,
            target_id=link_data.target_id,
            metadata_json=link_data.metadata,
        )
        self.session.add(link)
        await self.session.flush()
        await self.session.refresh(link)
        return link

    async def get_link(self, link_id: int) -> Optional[Link]:
        return await self.session.get(Link, link_id)

    async def list_links(
        self,
        source_id: Optional[int] = None,
        target_id: Optional[int] = None,
        type_id: Optional[int] = None,
        limit: int = 100,
    ) -> List[Link]:
        query = select(Link)
        if source_id:
            query = query.where(Link.source_id == source_id)
        if target_id:
            query = query.where(Link.target_id == target_id)
        if type_id:
            query = query.where(Link.type_id == type_id)
        result = await self.session.execute(query.limit(limit))
        return list(result.scalars().all())

    async def delete_link(self, link_id: int) -> bool:
        link = await self.get_link(link_id)
        if not link:
            return False
        await self.session.delete(link)
        await self.session.flush()
        return True
