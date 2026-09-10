"""动作 REST API：动作类型 + 执行入口"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from pydantic import BaseModel

from yuanzhu.db.database import get_db
from yuanzhu.ontology.action_store import ActionStore
from yuanzhu.staged.state_machine import StagedStateMachine
from yuanzhu.models.action import ActionTypeCreate, ActionTypeResponse, ActionExecResponse

router = APIRouter(prefix="/api/actions", tags=["actions"])


class ActionExecuteRequest(BaseModel):
    action_type_id: int
    params: dict = {}
    staged_by: Optional[str] = "api_user"
    idempotency_key: Optional[str] = None


@router.post("/types", response_model=ActionTypeResponse)
async def create_action_type(type_data: ActionTypeCreate, db: AsyncSession = Depends(get_db)):
    """创建/更新动作类型（upsert）"""
    return await ActionStore(db).create_type(type_data)


@router.get("/types", response_model=List[ActionTypeResponse])
async def list_action_types(domain: Optional[str] = None, db: AsyncSession = Depends(get_db)):
    return await ActionStore(db).list_types(domain=domain)


@router.post("/execute", response_model=ActionExecResponse)
async def execute_action(req: ActionExecuteRequest, db: AsyncSession = Depends(get_db)):
    """执行动作：写操作默认 staged（autonomy 策略见 StagedStateMachine）"""
    try:
        return await StagedStateMachine(db).stage(
            action_type_id=req.action_type_id,
            params=req.params,
            staged_by=req.staged_by or "api_user",
            idempotency_key=req.idempotency_key,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
