"""pytest fixtures：内存数据库 + 示例数据"""
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from yuanzhu.db.database import Base
from yuanzhu.db import models  # noqa: F401 确保模型注册到 metadata


@pytest_asyncio.fixture
async def db_engine():
    """内存数据库引擎（每个测试独立）"""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False, future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(db_engine):
    """数据库会话"""
    factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with factory() as session:
        yield session


@pytest_asyncio.fixture
async def sample_object_type(db_session):
    """示例对象类型：Bug"""
    obj_type = models.ObjectType(
        domain="test",
        name="Bug",
        title_key="title",
        description="测试用 Bug 类型",
        schema_json={
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "status": {"type": "string", "enum": ["Open", "Closed"]},
                "priority": {"type": "integer"},
            },
            "required": ["title"],
        },
        exposed=True,
    )
    db_session.add(obj_type)
    await db_session.commit()
    await db_session.refresh(obj_type)
    return obj_type


@pytest_asyncio.fixture
async def sample_action_type(db_session, sample_object_type):
    """示例动作类型：ChangePriority（含 transform 规则 + submission criteria）"""
    action_type = models.ActionType(
        domain="test",
        name="ChangePriority",
        params_schema_json={
            "type": "object",
            "properties": {
                "object_id": {"type": "integer"},
                "priority": {"type": "integer"},
            },
            "required": ["object_id", "priority"],
        },
        submission_criteria_json={
            # params.object_id 指向的对象，其 properties.status 必须为 Open
            "object_ref": "params.object_id",
            "check": {"properties.status": "Open"},
        },
        transform_json=[
            {"set": "properties.priority", "from": "params.priority"},
        ],
        side_effects_json=None,
        autonomy_level=2,
        requires_staging=True,
        description_for_agent="修改 Bug 优先级。只有 Open 状态的 Bug 才能修改优先级。",
        idempotency_key_template="{object_id}-{name}",
    )
    db_session.add(action_type)
    await db_session.commit()
    await db_session.refresh(action_type)
    return action_type
