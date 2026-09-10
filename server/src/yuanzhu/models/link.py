"""链接类型与实例的 Pydantic 模型"""
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any


class LinkTypeCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    domain: str = Field(..., min_length=1, max_length=100)
    source_type_id: int
    target_type_id: int
    cardinality: str = Field(default="many", pattern="^(one|many)$")


class LinkTypeResponse(BaseModel):
    id: int
    name: str
    domain: str
    source_type_id: int
    target_type_id: int
    cardinality: str

    model_config = {"from_attributes": True}


class LinkCreate(BaseModel):
    type_id: int
    source_id: int
    target_id: int
    metadata: Optional[Dict[str, Any]] = None


class LinkResponse(BaseModel):
    id: int
    type_id: int
    source_id: int
    target_id: int
    metadata: Optional[Dict[str, Any]] = None

    model_config = {"from_attributes": True}
