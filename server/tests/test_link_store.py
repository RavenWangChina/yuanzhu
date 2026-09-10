"""链接存储层（LinkStore）测试：类型 + 实例 + cardinality 约束"""
import pytest

from yuanzhu.ontology.link_store import LinkStore
from yuanzhu.models.link import LinkTypeCreate, LinkCreate
from yuanzhu.ontology.object_store import ObjectStore
from yuanzhu.models.object import ObjectTypeCreate, ObjectCreate


async def _make_two_types(db_session, sample_object_type):
    """造两个对象类型 + LinkStore/ObjectStore"""
    obj_store = ObjectStore(db_session)
    link_store = LinkStore(db_session)
    target_type = await obj_store.create_type(ObjectTypeCreate(
        name="TestCase",
        domain="test",
        properties={"name": {"type": "string", "required": True}},
    ))
    return obj_store, link_store, target_type


async def test_create_link_type(db_session, sample_object_type):
    _, link_store, target_type = await _make_two_types(db_session, sample_object_type)
    link_type = await link_store.create_type(LinkTypeCreate(
        name="has_testcase",
        domain="test",
        source_type_id=sample_object_type.id,
        target_type_id=target_type.id,
        cardinality="many",
    ))
    assert link_type.id is not None
    assert link_type.cardinality == "many"


async def test_link_type_upsert(db_session, sample_object_type):
    _, link_store, target_type = await _make_two_types(db_session, sample_object_type)
    first = await link_store.create_type(LinkTypeCreate(
        name="has_testcase", domain="test",
        source_type_id=sample_object_type.id, target_type_id=target_type.id,
    ))
    second = await link_store.create_type(LinkTypeCreate(
        name="has_testcase", domain="test",
        source_type_id=sample_object_type.id, target_type_id=target_type.id,
        cardinality="one",
    ))
    assert second.id == first.id
    assert second.cardinality == "one"


async def test_register_link_type_by_name(db_session, sample_object_type):
    """DSL 用类型名引用，注册期解析为 type_id（模板注册路径）"""
    _, link_store, target_type = await _make_two_types(db_session, sample_object_type)
    link_type = await link_store.register_type_by_name(
        domain="test", name="has_testcase",
        source_type="Bug", target_type="TestCase",
    )
    assert link_type.source_type_id == sample_object_type.id
    assert link_type.target_type_id == target_type.id


async def test_create_and_list_links(db_session, sample_object_type):
    obj_store, link_store, target_type = await _make_two_types(db_session, sample_object_type)
    link_type = await link_store.create_type(LinkTypeCreate(
        name="has_testcase", domain="test",
        source_type_id=sample_object_type.id, target_type_id=target_type.id,
    ))
    source_obj = await obj_store.create_object(ObjectCreate(
        type_id=sample_object_type.id, properties={"title": "Bug-1", "status": "Open"},
    ))
    for i in range(3):
        target_obj = await obj_store.create_object(ObjectCreate(
            type_id=target_type.id, properties={"name": f"TC-{i}"},
        ))
        await link_store.create_link(LinkCreate(
            type_id=link_type.id, source_id=source_obj.id, target_id=target_obj.id,
        ))

    links = await link_store.list_links(source_id=source_obj.id)
    assert len(links) == 3
    by_target = await link_store.list_links(
        target_id=(await obj_store.list_objects(type_id=target_type.id))[0].id
    )
    assert len(by_target) == 1


async def test_one_cardinality_enforced(db_session, sample_object_type):
    """cardinality=one 时重复链接被拒"""
    obj_store, link_store, target_type = await _make_two_types(db_session, sample_object_type)
    link_type = await link_store.create_type(LinkTypeCreate(
        name="primary_testcase", domain="test",
        source_type_id=sample_object_type.id, target_type_id=target_type.id,
        cardinality="one",
    ))
    source_obj = await obj_store.create_object(ObjectCreate(
        type_id=sample_object_type.id, properties={"title": "Bug-独占", "status": "Open"},
    ))
    t1 = await obj_store.create_object(ObjectCreate(type_id=target_type.id, properties={"name": "TC-A"}))
    t2 = await obj_store.create_object(ObjectCreate(type_id=target_type.id, properties={"name": "TC-B"}))

    await link_store.create_link(LinkCreate(
        type_id=link_type.id, source_id=source_obj.id, target_id=t1.id,
    ))
    with pytest.raises(ValueError, match="one"):
        await link_store.create_link(LinkCreate(
            type_id=link_type.id, source_id=source_obj.id, target_id=t2.id,
        ))


async def test_delete_link(db_session, sample_object_type):
    obj_store, link_store, target_type = await _make_two_types(db_session, sample_object_type)
    link_type = await link_store.create_type(LinkTypeCreate(
        name="temp_link", domain="test",
        source_type_id=sample_object_type.id, target_type_id=target_type.id,
    ))
    s = await obj_store.create_object(ObjectCreate(type_id=sample_object_type.id, properties={"title": "s"}))
    t = await obj_store.create_object(ObjectCreate(type_id=target_type.id, properties={"name": "t"}))
    link = await link_store.create_link(LinkCreate(
        type_id=link_type.id, source_id=s.id, target_id=t.id,
    ))
    assert await link_store.delete_link(link.id) is True
    assert await link_store.get_link(link.id) is None
