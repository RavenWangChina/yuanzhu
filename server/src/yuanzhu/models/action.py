"""动作类型与执行记录的 Pydantic 模型"""
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime


class ActionTypeCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    domain: str = Field(..., min_length=1, max_length=100)
    params_schema: Dict[str, Any] = Field(default_factory=dict)
    submission_criteria: Optional[Dict[str, Any]] = None
    transform: Optional[List[Dict[str, Any]]] = None
    side_effects: Optional[List[Dict[str, Any]]] = None
    autonomy_level: int = Field(default=2, ge=1, le=5)
    requires_staging: bool = True
    description_for_agent: Optional[str] = None
    idempotency_key_template: Optional[str] = None


class ActionTypeResponse(BaseModel):
    id: int
    name: str
    domain: str
    params_schema: Dict[str, Any]
    autonomy_level: int
    requires_staging: bool
    description_for_agent: Optional[str] = None

    model_config = {"from_attributes": True}


class ActionExecResponse(BaseModel):
    id: int
    action_type_id: int
    params: Dict[str, Any]
    idempotency_key: Optional[str] = None
    status: str
    staged_by: Optional[str] = None
    staged_at: datetime
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    review_comment: Optional[str] = None
    applied_at: Optional[datetime] = None
    reverted_at: Optional[datetime] = None
    exec_log: Optional[Dict[str, Any]] = None

    model_config = {"from_attributes": True}
