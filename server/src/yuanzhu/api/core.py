"""节点 / 任务 / 模板 REST API（dsh-edge 与 Web 控制台的前置接口，ADR-003）"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from pydantic import BaseModel
from pathlib import Path

from yuanzhu.db.database import get_db
from yuanzhu.node.store import NodeStore
from yuanzhu.node.models import NodeCreate, NodeHeartbeat, NodeResponse
from yuanzhu.task.orchestrator import TaskOrchestrator
from yuanzhu.task.models import TaskCreate, TaskStatusUpdate, TaskResponse
from yuanzhu.template.store import TemplateStore

router = APIRouter(prefix="/api", tags=["core"])


# ---------- 节点 ----------

@router.post("/nodes/register", response_model=NodeResponse)
async def register_node(body: NodeCreate, db: AsyncSession = Depends(get_db)):
    return await NodeStore(db).register(body)


@router.post("/nodes/{node_id}/heartbeat", response_model=NodeResponse)
async def node_heartbeat(node_id: int, body: NodeHeartbeat, db: AsyncSession = Depends(get_db)):
    try:
        return await NodeStore(db).heartbeat(node_id, body)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/nodes", response_model=list[NodeResponse])
async def list_nodes(status: Optional[str] = None, db: AsyncSession = Depends(get_db)):
    return await NodeStore(db).list(status=status)


# ---------- 任务 ----------

@router.post("/tasks", response_model=TaskResponse)
async def create_task(body: TaskCreate, db: AsyncSession = Depends(get_db)):
    return await TaskOrchestrator(db).create(body)


@router.get("/tasks", response_model=list[TaskResponse])
async def list_tasks(
    status: Optional[str] = None,
    node_id: Optional[int] = None,
    created_by: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    return await TaskOrchestrator(db).list(status=status, node_id=node_id, created_by=created_by)


@router.get("/tasks/{task_id}", response_model=TaskResponse)
async def get_task(task_id: int, db: AsyncSession = Depends(get_db)):
    task = await TaskOrchestrator(db).get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    return task


@router.post("/tasks/{task_id}/dispatch/{node_id}", response_model=TaskResponse)
async def dispatch_task(task_id: int, node_id: int, db: AsyncSession = Depends(get_db)):
    try:
        return await TaskOrchestrator(db).dispatch(task_id, node_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/tasks/{task_id}/report", response_model=TaskResponse)
async def report_task(task_id: int, body: TaskStatusUpdate, db: AsyncSession = Depends(get_db)):
    try:
        return await TaskOrchestrator(db).report(task_id, body)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/nodes/{node_id}/tasks/pull", response_model=list[TaskResponse])
async def pull_tasks(node_id: int, limit: int = 10, db: AsyncSession = Depends(get_db)):
    """dsh-edge 拉任务（pull 模式）"""
    return await TaskOrchestrator(db).pull(node_id, limit=limit)


# ---------- 模板 ----------

class TemplateRegisterRequest(BaseModel):
    path: str  # v0.1 本地目录注册；zip 上传留后续里程碑


@router.post("/templates/register")
async def register_template(body: TemplateRegisterRequest, db: AsyncSession = Depends(get_db)):
    tpl_dir = Path(body.path)
    if not tpl_dir.is_dir():
        raise HTTPException(status_code=400, detail=f"模板目录不存在: {body.path}")
    try:
        return await TemplateStore(db).register_dir(tpl_dir)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/templates")
async def list_templates(domain: Optional[str] = None, status: Optional[str] = None,
                         db: AsyncSession = Depends(get_db)):
    return await TemplateStore(db).list(domain=domain, status=status)


# ---------- 用量与审计 ----------

@router.get("/usage")
async def usage_summary(
    days: int = 7,
    db: AsyncSession = Depends(get_db),
):
    """模型用量汇总（按模型分组：调用数/token/估费）+ 最近明细"""
    from datetime import timedelta
    from sqlalchemy import func as sa_func, select as sa_select
    from yuanzhu.db.models import ModelUsage, utcnow

    cutoff = utcnow() - timedelta(days=days)
    grouped = await db.execute(
        sa_select(
            ModelUsage.model,
            sa_func.count(ModelUsage.id),
            sa_func.sum(ModelUsage.prompt_tokens),
            sa_func.sum(ModelUsage.completion_tokens),
            sa_func.sum(ModelUsage.estimated_cost),
        ).where(ModelUsage.created_at >= cutoff).group_by(ModelUsage.model)
    )
    summary = [
        {
            "model": row[0], "calls": row[1],
            "prompt_tokens": row[2] or 0, "completion_tokens": row[3] or 0,
            "estimated_cost": row[4] or 0.0,
        }
        for row in grouped.all()
    ]

    recent = await db.execute(
        sa_select(ModelUsage).where(ModelUsage.created_at >= cutoff)
        .order_by(ModelUsage.created_at.desc()).limit(50)
    )
    details = [
        {
            "id": u.id, "model": u.model, "task_id": u.task_id, "caller": u.caller,
            "prompt_tokens": u.prompt_tokens, "completion_tokens": u.completion_tokens,
            "estimated_cost": u.estimated_cost, "created_at": u.created_at.isoformat(),
        }
        for u in recent.scalars().all()
    ]
    return {"days": days, "summary": summary, "recent": details}
