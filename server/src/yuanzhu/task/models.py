"""任务 Pydantic DTO"""
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional
from datetime import datetime


class TaskCreate(BaseModel):
    template_id: Optional[int] = None
    template_version: Optional[str] = None
    params: Dict[str, Any] = Field(default_factory=dict)
    created_by: Optional[str] = None


class TaskStatusUpdate(BaseModel):
    status: str  # dispatched | running | done | failed | cancelled
    result: Optional[Dict[str, Any]] = None
    exec_log: Optional[Dict[str, Any]] = None


class TaskResponse(BaseModel):
    id: int
    template_id: Optional[int] = None
    template_version: Optional[str] = None
    params: Dict[str, Any]
    status: str
    assigned_node_id: Optional[int] = None
    result: Optional[Dict[str, Any]] = None
    exec_log: Optional[Dict[str, Any]] = None
    created_by: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None

    model_config = {"from_attributes": True}
