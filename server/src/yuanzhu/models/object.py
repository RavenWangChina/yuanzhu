"""对象类型与实例的 Pydantic 模型（API 层 DTO）"""
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime


class ObjectTypeCreate(BaseModel):
    """创建/更新对象类型"""
    name: str = Field(..., min_length=1, max_length=100)
    domain: str = Field(..., min_length=1, max_length=100)
    title_key: Optional[str] = None
    description: Optional[str] = None
    properties: Dict[str, Any] = Field(default_factory=dict)  # 简写 DSL
    exposed: bool = False


class ObjectTypeResponse(BaseModel):
    id: int
    name: str
    domain: str
    title_key: Optional[str] = None
    description: Optional[str] = None
    schema_json: Dict[str, Any]
    exposed: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class ObjectCreate(BaseModel):
    type_id: int
    properties: Dict[str, Any] = Field(default_factory=dict)
    title: Optional[str] = None
    created_by: Optional[str] = None


class ObjectUpdate(BaseModel):
    properties: Optional[Dict[str, Any]] = None
    title: Optional[str] = None


class ObjectResponse(BaseModel):
    id: int
    type_id: int
    properties: Dict[str, Any]
    title: Optional[str] = None
    created_by: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
