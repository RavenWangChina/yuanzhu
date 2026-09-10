"""Task 1 冒烟测试：数据库模型可建表、可插入、可查询"""
import pytest

from yuanzhu.db import models


async def test_object_type_roundtrip(db_session):
    """对象类型可插入并读回"""
    obj_type = models.ObjectType(
        domain="test",
        name="SmokeType",
        title_key="title",
        schema_json={"type": "object", "properties": {"title": {"type": "string"}}},
        exposed=False,
    )
    db_session.add(obj_type)
    await db_session.commit()
    await db_session.refresh(obj_type)

    assert obj_type.id is not None
    assert obj_type.created_at is not None
    fetched = await db_session.get(models.ObjectType, obj_type.id)
    assert fetched.name == "SmokeType"


async def test_action_type_fields(db_session, sample_action_type):
    """动作类型含 transform 规则与自主性字段（对抗审查修订项）"""
    assert sample_action_type.transform_json == [
        {"set": "properties.priority", "from": "params.priority"}
    ]
    assert sample_action_type.autonomy_level == 2
    assert sample_action_type.requires_staging is True
    assert sample_action_type.submission_criteria_json["check"] == {"properties.status": "Open"}


async def test_action_exec_status_default(db_session, sample_action_type):
    """动作执行记录默认 staged 状态"""
    exec = models.ActionExec(
        action_type_id=sample_action_type.id,
        params_json={"object_id": 1, "priority": 3},
        staged_by="smoke",
    )
    db_session.add(exec)
    await db_session.commit()
    await db_session.refresh(exec)

    assert exec.status == "staged"
    assert exec.staged_at is not None
