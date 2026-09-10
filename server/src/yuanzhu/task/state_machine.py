"""任务状态机：合法转换表 + 终态时间戳"""
from sqlalchemy.ext.asyncio import AsyncSession

from yuanzhu.db.models import Task, utcnow

VALID_TRANSITIONS = {
    "pending": {"dispatched", "cancelled"},
    "dispatched": {"running", "cancelled"},
    "running": {"done", "failed", "cancelled"},
    "done": set(),
    "failed": set(),
    "cancelled": set(),
}


class TaskStateMachine:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def transition(self, task_id: int, new_status: str) -> Task:
        task = await self.session.get(Task, task_id)
        if not task:
            raise ValueError(f"任务不存在: {task_id}")

        allowed = VALID_TRANSITIONS.get(task.status, set())
        if new_status not in allowed:
            raise ValueError(
                f"非法状态转换: {task.status} → {new_status}"
                f"（允许: {sorted(allowed) or ['（终态）']}）"
            )
        task.status = new_status
        if new_status in ("done", "failed", "cancelled"):
            task.completed_at = utcnow()
        await self.session.flush()
        await self.session.refresh(task)
        return task
