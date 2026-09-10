"""节点存储：注册（upsert）/ 心跳 / 状态 / 过期下线"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional
from datetime import datetime, timezone, timedelta

from yuanzhu.db.models import Node, utcnow
from yuanzhu.node.models import NodeCreate, NodeHeartbeat


class NodeStore:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def register(self, node_data: NodeCreate) -> Node:
        """注册节点（同名 upsert：重装/重启场景复用记录）"""
        existing = await self.get_by_name(node_data.name)
        if existing:
            existing.token = node_data.token
            existing.capabilities = node_data.capabilities
            existing.status = "online"
            existing.last_heartbeat = utcnow()
            await self.session.flush()
            return existing

        node = Node(
            name=node_data.name,
            token=node_data.token,
            capabilities=node_data.capabilities,
            status="online",
            last_heartbeat=utcnow(),
        )
        self.session.add(node)
        await self.session.flush()
        await self.session.refresh(node)
        return node

    async def heartbeat(self, node_id: int, hb: NodeHeartbeat) -> Node:
        node = await self.get(node_id)
        if not node:
            raise ValueError(f"节点不存在: {node_id}")
        node.status = hb.status
        node.current_task_id = hb.current_task_id
        node.resource_usage = hb.resource_usage
        node.last_heartbeat = utcnow()
        await self.session.flush()
        await self.session.refresh(node)
        return node

    async def get(self, node_id: int) -> Optional[Node]:
        return await self.session.get(Node, node_id)

    async def get_by_name(self, name: str) -> Optional[Node]:
        result = await self.session.execute(select(Node).where(Node.name == name))
        return result.scalar_one_or_none()

    async def get_by_token(self, token: str) -> Optional[Node]:
        result = await self.session.execute(select(Node).where(Node.token == token))
        return result.scalar_one_or_none()

    async def list(self, status: Optional[str] = None, limit: int = 100) -> List[Node]:
        query = select(Node)
        if status:
            query = query.where(Node.status == status)
        result = await self.session.execute(query.order_by(Node.registered_at).limit(limit))
        return list(result.scalars().all())

    async def update_status(self, node_id: int, status: str) -> Node:
        node = await self.get(node_id)
        if not node:
            raise ValueError(f"节点不存在: {node_id}")
        node.status = status
        await self.session.flush()
        await self.session.refresh(node)
        return node

    async def mark_stale_offline(self, timeout_seconds: int = 180) -> int:
        """心跳超时的 online/busy 节点标为 offline（60s 心跳 ×3 容忍）；返回下线数"""
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=timeout_seconds)
        result = await self.session.execute(
            select(Node).where(
                Node.status.in_(["online", "busy"]),
                Node.last_heartbeat < cutoff,
            )
        )
        stale = list(result.scalars().all())
        for node in stale:
            node.status = "offline"
        await self.session.flush()
        return len(stale)
