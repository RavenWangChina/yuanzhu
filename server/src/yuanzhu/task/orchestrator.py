"""任务编排器：创建 / 分发（按在线节点）/ 节点 pull / 结果回报"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional

from yuanzhu.db.models import Task, Node
from yuanzhu.task.models import TaskCreate, TaskStatusUpdate
from yuanzhu.task.state_machine import TaskStateMachine


class TaskOrchestrator:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.sm = TaskStateMachine(session)

    async def create(self, data: TaskCreate) -> Task:
        task = Task(
            template_id=data.template_id,
            template_version=data.template_version,
            params_json=data.params,
            status="pending",
            created_by=data.created_by,
        )
        self.session.add(task)
        await self.session.flush()
        await self.session.refresh(task)
        return task

    async def dispatch(self, task_id: int, node_id: int) -> Task:
        """分发到指定节点（节点须在线；调度策略 v0.1 由调用方选节点）"""
        node = await self.session.get(Node, node_id)
        if not node:
            raise ValueError(f"节点不存在: {node_id}")
        if node.status not in ("online", "busy"):
            raise ValueError(f"节点不在线: {node.status}")

        task = await self.session.get(Task, task_id)
        if not task:
            raise ValueError(f"任务不存在: {task_id}")
        task.assigned_node_id = node_id
        await self.sm.transition(task_id, "dispatched")
        await self.session.refresh(task)
        return task

    async def pull(self, node_id: int, limit: int = 10) -> List[Task]:
        """节点拉取分派给它的任务并标记 running（pull 模式，免 NAT 穿透）"""
        result = await self.session.execute(
            select(Task).where(
                Task.assigned_node_id == node_id,
                Task.status == "dispatched",
            ).limit(limit)
        )
        tasks = list(result.scalars().all())
        for task in tasks:
            await self.sm.transition(task.id, "running")
        return tasks

    async def report(self, task_id: int, update: TaskStatusUpdate) -> Task:
        """节点回报终态：结果与执行日志落库"""
        task = await self.sm.transition(task_id, update.status)
        if update.result is not None:
            task.result_json = update.result
        if update.exec_log is not None:
            task.exec_log_json = update.exec_log
        await self.session.flush()
        await self.session.refresh(task)
        return task

    async def list(
        self,
        status: Optional[str] = None,
        node_id: Optional[int] = None,
        created_by: Optional[str] = None,
        limit: int = 100,
    ) -> List[Task]:
        query = select(Task)
        if status:
            query = query.where(Task.status == status)
        if node_id:
            query = query.where(Task.assigned_node_id == node_id)
        if created_by:
            query = query.where(Task.created_by == created_by)
        result = await self.session.execute(query.order_by(Task.created_at.desc()).limit(limit))
        return list(result.scalars().all())

    async def get(self, task_id: int) -> Optional[Task]:
        return await self.session.get(Task, task_id)
