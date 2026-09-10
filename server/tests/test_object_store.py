"""对象存储层（ObjectStore）CRUD + schema 校验测试"""
import pytest

from yuanzhu.ontology.object_store import ObjectStore
from yuanzhu.models.object import ObjectTypeCreate, ObjectCreate, ObjectUpdate


async def test_create_object_type(db_session):
    """创建对象类型"""
    store = ObjectStore(db_session)
    obj_type = await store.create_type(ObjectTypeCreate(
        name="TestCase",
        domain="aiqa",
        title_key="name",
        description="测试用例类型",
        properties={
            "name": {"type": "string", "required": True},
            "status": {"type": "string", "enum": ["Active", "Inactive"], "default": "Active"},
        },
        exposed=True,
    ))
    assert obj_type.id is not None
    assert obj_type.schema_json["required"] == ["name"]


async def test_create_type_upsert(db_session, sample_object_type):
    """同名类型 upsert（模板注册幂等）"""
    store = ObjectStore(db_session)
    updated = await store.create_type(ObjectTypeCreate(
        name="Bug",  # 与 sample_object_type 同 domain+name
        domain="test",
        title_key="title",
        description="更新后的描述",
        properties={"title": {"type": "string", "required": True}},
        exposed=False,
    ))
    assert updated.id == sample_object_type.id  # 同一条记录
    assert updated.description == "更新后的描述"


async def test_create_object_extracts_title(db_session, sample_object_type):
    """创建对象时从 title_key 自动提取标题"""
    store = ObjectStore(db_session)
    obj = await store.create_object(ObjectCreate(
        type_id=sample_object_type.id,
        properties={"title": "登录页崩溃", "status": "Open", "priority": 3},
        created_by="test_user",
    ))
    assert obj.id is not None
    assert obj.title == "登录页崩溃"


async def test_create_object_invalid_enum_rejected(db_session, sample_object_type):
    """属性不符合 schema（enum 越界）被拒"""
    store = ObjectStore(db_session)
    with pytest.raises(ValueError, match="验证失败"):
        await store.create_object(ObjectCreate(
            type_id=sample_object_type.id,
            properties={"title": "坏状态", "status": "Bogus"},  # 不在 enum
        ))


async def test_create_object_missing_required_rejected(db_session, sample_object_type):
    """缺 required 属性被拒"""
    store = ObjectStore(db_session)
    with pytest.raises(ValueError, match="验证失败"):
        await store.create_object(ObjectCreate(
            type_id=sample_object_type.id,
            properties={"status": "Open"},  # 缺 title
        ))


async def test_list_objects_filter(db_session, sample_object_type):
    """按类型列出对象"""
    store = ObjectStore(db_session)
    for i in range(5):
        await store.create_object(ObjectCreate(
            type_id=sample_object_type.id,
            properties={"title": f"Bug-{i}", "status": "Open"},
        ))
    objects = await store.list_objects(type_id=sample_object_type.id)
    assert len(objects) == 5


async def test_list_objects_by_domain(db_session, sample_object_type):
    """按 domain 列出对象（join object_type）"""
    store = ObjectStore(db_session)
    await store.create_object(ObjectCreate(
        type_id=sample_object_type.id,
        properties={"title": "域过滤测试", "status": "Open"},
    ))
    objects = await store.list_objects(domain="test")
    assert len(objects) >= 1
    assert all(o.object_type.domain == "test" for o in objects)


async def test_update_object_merges(db_session, sample_object_type):
    """更新对象：属性合并 + 标题重提取"""
    store = ObjectStore(db_session)
    obj = await store.create_object(ObjectCreate(
        type_id=sample_object_type.id,
        properties={"title": "原标题", "status": "Open"},
    ))
    updated = await store.update_object(obj.id, ObjectUpdate(
        properties={"title": "新标题", "status": "Closed", "priority": 1},
    ))
    assert updated.properties["status"] == "Closed"
    assert updated.title == "新标题"


async def test_delete_object(db_session, sample_object_type):
    """删除对象"""
    store = ObjectStore(db_session)
    obj = await store.create_object(ObjectCreate(
        type_id=sample_object_type.id,
        properties={"title": "待删除"},
    ))
    assert await store.delete_object(obj.id) is True
    assert await store.get_object(obj.id) is None
    assert await store.delete_object(99999) is False


async def test_get_type_by_name(db_session, sample_object_type):
    """按 domain+name 查类型"""
    store = ObjectStore(db_session)
    found = await store.get_type_by_name("test", "Bug")
    assert found.id == sample_object_type.id
    assert await store.get_type_by_name("test", "NoSuch") is None
