"""节点 Pydantic DTO"""
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional
from datetime import datetime


class NodeCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    token: str = Field(..., min_length=1)
    capabilities: Dict[str, Any] = Field(default_factory=dict)


class NodeHeartbeat(BaseModel):
    status: str = "online"
    current_task_id: Optional[int] = None
    resource_usage: Optional[Dict[str, Any]] = None


class NodeResponse(BaseModel):
    id: int
    name: str
    status: str
    capabilities: Dict[str, Any]
    current_task_id: Optional[int] = None
    resource_usage: Optional[Dict[str, Any]] = None
    last_heartbeat: Optional[datetime] = None
    registered_at: datetime

    model_config = {"from_attributes": True}
