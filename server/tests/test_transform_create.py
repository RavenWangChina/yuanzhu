"""transform 规则引擎扩展测试：create_object（建对象类动作）+ 补偿删除"""
import pytest

from yuanzhu.staged.state_machine import StagedStateMachine
from yuanzhu.ontology.object_store import ObjectStore
from yuanzhu.ontology.action_store import ActionStore
from yuanzhu.models.object import ObjectCreate
from yuanzhu.models.action import ActionTypeCreate


async def _make_create_bug_action(db_session, sample_object_type):
    store = ActionStore(db_session)
    return await store.create_type(ActionTypeCreate(
        name="CreateBug",
        domain="test",
        params_schema={
            "type": "object",
            "properties": {"title": {"type": "string"}, "severity": {"type": "string"}},
            "required": ["title"],
        },
        transform=[{
            "create_object": {"type": "Bug"},
            "with": {"title": "from:params.title", "status": "literal:Open"},
        }],
        autonomy_level=2,
        requires_staging=True,
        description_for_agent="创建新 Bug",
    ))


async def test_create_object_applied(db_session, sample_object_type):
    """批准后创建对象，with 规则解析 from/literal"""
    sm = StagedStateMachine(db_session)
    action = await _make_create_bug_action(db_session, sample_object_type)

    exec = await sm.stage(
        action.id,
        {"title": "新发现缺陷", "severity": "high"},
        staged_by="qa-agent",
    )
    await sm.approve(exec.id, reviewed_by="r")
    applied = await sm.apply(exec.id)

    obj_store = ObjectStore(db_session)
    bugs = await obj_store.list_objects(type_id=sample_object_type.id)
    assert len(bugs) == 1
    assert bugs[0].properties["title"] == "新发现缺陷"
    assert bugs[0].properties["status"] == "Open"       # literal
    assert bugs[0].created_by == "qa-agent"

    # 执行日志记录了新建对象 id（供补偿）
    assert applied.exec_log_json["created_object_ids"] == [bugs[0].id]


async def test_create_object_revert_deletes(db_session, sample_object_type):
    """撤销 = 删除补偿（建的对象被删掉）"""
    sm = StagedStateMachine(db_session)
    action = await _make_create_bug_action(db_session, sample_object_type)
    obj_store = ObjectStore(db_session)

    exec = await sm.stage(action.id, {"title": "会撤掉的"}, staged_by="qa-agent")
    await sm.approve(exec.id, reviewed_by="r")
    await sm.apply(exec.id)
    assert len(await obj_store.list_objects(type_id=sample_object_type.id)) == 1

    await sm.revert(exec.id)
    assert len(await obj_store.list_objects(type_id=sample_object_type.id)) == 0


async def test_create_object_unknown_type_rejected(db_session, sample_object_type):
    """create_object 引用未注册类型 → stage 时即报错（不是 apply 时）"""
    store = ActionStore(db_session)
    action = await store.create_type(ActionTypeCreate(
        name="BadCreate",
        domain="test",
        params_schema={"type": "object", "properties": {"t": {"type": "string"}}},
        transform=[{"create_object": {"type": "NoSuchType"}, "with": {}}],
    ))
    sm = StagedStateMachine(db_session)
    with pytest.raises(ValueError, match="NoSuchType"):
        await sm.stage(action.id, {"t": "x"}, staged_by="a")
