"""审批 REST API（待审中心的后端）：pending 列表 / approve / reject / revert"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from pydantic import BaseModel

from yuanzhu.db.database import get_db
from yuanzhu.staged.state_machine import StagedStateMachine
from yuanzhu.models.action import ActionExecResponse

router = APIRouter(prefix="/api/staged", tags=["staged"])


class ReviewRequest(BaseModel):
    reviewed_by: str = "web_reviewer"
    review_comment: Optional[str] = None


class RejectRequest(BaseModel):
    reviewed_by: str = "web_reviewer"
    review_comment: str  # 拒绝必须带理由


@router.get("/pending")
async def list_pending(db: AsyncSession = Depends(get_db)):
    """待审列表（带审批上下文：动作/参数/暂存者/before 快照）"""
    pending = await StagedStateMachine(db).list_pending()

    from yuanzhu.ontology.action_store import ActionStore
    action_store = ActionStore(db)
    items = []
    for exec in pending:
        action_type = await action_store.get_type(exec.action_type_id)
        items.append({
            "id": exec.id,
            "action": f"{action_type.domain}/{action_type.name}" if action_type else "?",
            # H2：小白可读的动作说明（来自 description_for_agent）
            "action_description": (action_type.description_for_agent if action_type else None),
            "params": exec.params_json,
            "staged_by": exec.staged_by,
            "staged_at": exec.staged_at,
            "before": (exec.exec_log_json or {}).get("before"),
        })
    return items


@router.post("/{exec_id}/approve", response_model=ActionExecResponse)
async def approve(exec_id: int, req: ReviewRequest, db: AsyncSession = Depends(get_db)):
    """批准（自动应用 transform）；v0.1.3：采纳深度答案时自动触发洞见提炼（采纳即沉淀）"""
    sm = StagedStateMachine(db)
    try:
        exec = await sm.approve(exec_id, reviewed_by=req.reviewed_by, review_comment=req.review_comment)
        applied = await sm.apply(exec_id)

        # 采纳即沉淀：metaflow 的答案被采纳 → 同事务自动提炼洞见（staged 轻确认）
        from sqlalchemy import select as _sel
        from yuanzhu.db.models import ActionType
        at = (await db.execute(_sel(ActionType).where(ActionType.id == exec.action_type_id))).scalar_one_or_none()
        if at and at.domain == "metaflow" and at.name == "SaveAnswer":
            try:
                from yuanzhu.workflow.engine import WorkflowEngine
                params = exec.params_json or {}
                await WorkflowEngine(db).run(
                    domain="metaflow", workflow_name="distill-insight",
                    params={"question": params.get("question", ""),
                            "answer": params.get("content", "")},
                    run_by="auto-distill",
                )
            except Exception:
                pass  # 沉淀失败不阻断采纳主流程（下次可手动 distill）

        return applied
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{exec_id}/reject", response_model=ActionExecResponse)
async def reject(exec_id: int, req: RejectRequest, db: AsyncSession = Depends(get_db)):
    """拒绝（必须附理由）"""
    try:
        return await StagedStateMachine(db).reject(
            exec_id, reviewed_by=req.reviewed_by, review_comment=req.review_comment
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{exec_id}/revert", response_model=ActionExecResponse)
async def revert(exec_id: int, db: AsyncSession = Depends(get_db)):
    """撤销已应用动作（补偿事务）"""
    try:
        return await StagedStateMachine(db).revert(exec_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
