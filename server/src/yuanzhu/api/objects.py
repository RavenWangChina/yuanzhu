"""对象 REST API：类型与实例的 CRUD"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional

from yuanzhu.db.database import get_db
from yuanzhu.ontology.object_store import ObjectStore
from yuanzhu.models.object import (
    ObjectTypeCreate, ObjectTypeResponse, ObjectCreate, ObjectResponse, ObjectUpdate,
)

router = APIRouter(prefix="/api/objects", tags=["objects"])


@router.post("/types", response_model=ObjectTypeResponse)
async def create_object_type(type_data: ObjectTypeCreate, db: AsyncSession = Depends(get_db)):
    """创建/更新对象类型（upsert）"""
    return await ObjectStore(db).create_type(type_data)


@router.get("/types", response_model=List[ObjectTypeResponse])
async def list_object_types(domain: Optional[str] = None, db: AsyncSession = Depends(get_db)):
    return await ObjectStore(db).list_types(domain=domain)


@router.post("", response_model=ObjectResponse)
async def create_object(obj_data: ObjectCreate, db: AsyncSession = Depends(get_db)):
    try:
        return await ObjectStore(db).create_object(obj_data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{obj_id}", response_model=ObjectResponse)
async def get_object(obj_id: int, db: AsyncSession = Depends(get_db)):
    obj = await ObjectStore(db).get_object(obj_id)
    if not obj:
        raise HTTPException(status_code=404, detail="对象不存在")
    return obj


@router.get("")
async def list_objects(
    domain: Optional[str] = None,
    type_id: Optional[int] = None,
    created_by: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    limit = min(max(limit, 1), 500)  # I5：钳制
    objects = await ObjectStore(db).list_objects(
        domain=domain, type_id=type_id, created_by=created_by, limit=limit, offset=offset
    )
    # 填充 object_type 信息（自举发现#1：知识库页面需要类型名）
    from yuanzhu.db.models import ObjectType as _OT
    type_map = {}
    for o in objects:
        if o.type_id not in type_map:
            type_map[o.type_id] = await db.get(_OT, o.type_id)
    result = []
    for o in objects:
        obj_dict = {
            "id": o.id, "type_id": o.type_id,
            "properties": o.properties_json or {},
            "title": o.title, "created_by": o.created_by,
            "created_at": o.created_at, "updated_at": o.updated_at,
            "object_type": {
                "name": type_map[o.type_id].name if type_map.get(o.type_id) else None,
                "domain": type_map[o.type_id].domain if type_map.get(o.type_id) else None,
            } if type_map.get(o.type_id) else None,
        }
        result.append(obj_dict)
    return result
