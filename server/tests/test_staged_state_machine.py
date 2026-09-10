"""Staged writes 状态机测试（对抗审查修订版架构）

覆盖：
- params schema 校验（JSON Schema 管格式）
- submission_criteria 运行时校验（语义：Open 才能改优先级）
- 幂等键防重
- autonomy_level L1 自动执行 / L2 staged 人审
- approve → apply（transform 规则引擎执行，非硬编码）
- reject（带理由）
- revert（补偿事务恢复原值）
"""
import pytest

from yuanzhu.staged.state_machine import StagedStateMachine
from yuanzhu.ontology.object_store import ObjectStore
from yuanzhu.ontology.action_store import ActionStore
from yuanzhu.models.object import ObjectCreate
from yuanzhu.models.action import ActionTypeCreate
from yuanzhu.db import models


async def _make_open_bug(db_session, sample_object_type, title="Bug-X", priority=1):
    store = ObjectStore(db_session)
    return await store.create_object(ObjectCreate(
        type_id=sample_object_type.id,
        properties={"title": title, "status": "Open", "priority": priority},
    ))


async def test_stage_creates_staged_record(db_session, sample_object_type, sample_action_type):
    sm = StagedStateMachine(db_session)
    bug = await _make_open_bug(db_session, sample_object_type)

    exec = await sm.stage(
        action_type_id=sample_action_type.id,
        params={"object_id": bug.id, "priority": 5},
        staged_by="test_agent",
        idempotency_key=f"{bug.id}-ChangePriority",
    )
    assert exec.status == "staged"
    assert exec.staged_by == "test_agent"
    assert exec.params_json["object_id"] == bug.id


async def test_stage_validates_params_schema(db_session, sample_object_type, sample_action_type):
    """params 不符合 schema（缺 priority）被拒"""
    sm = StagedStateMachine(db_session)
    bug = await _make_open_bug(db_session, sample_object_type)
    with pytest.raises(ValueError, match="参数验证失败"):
        await sm.stage(
            action_type_id=sample_action_type.id,
            params={"object_id": bug.id},  # 缺 priority
            staged_by="agent",
        )


async def test_stage_submission_criteria_blocks_closed_bug(db_session, sample_object_type, sample_action_type):
    """语义校验：Closed 的 Bug 不能改优先级（spec 3.1 核心场景）"""
    sm = StagedStateMachine(db_session)
    store = ObjectStore(db_session)
    closed_bug = await store.create_object(ObjectCreate(
        type_id=sample_object_type.id,
        properties={"title": "已关闭", "status": "Closed", "priority": 2},
    ))
    with pytest.raises(ValueError, match="submission_criteria|状态"):
        await sm.stage(
            action_type_id=sample_action_type.id,
            params={"object_id": closed_bug.id, "priority": 5},
            staged_by="agent",
        )


async def test_idempotency_returns_same_record(db_session, sample_object_type, sample_action_type):
    sm = StagedStateMachine(db_session)
    bug = await _make_open_bug(db_session, sample_object_type)
    key = f"{bug.id}-ChangePriority"
    e1 = await sm.stage(sample_action_type.id, {"object_id": bug.id, "priority": 3}, "a", key)
    e2 = await sm.stage(sample_action_type.id, {"object_id": bug.id, "priority": 3}, "a", key)
    assert e1.id == e2.id


async def test_l1_autonomy_auto_applies(db_session, sample_object_type):
    """L1 自主性：确定性读/转换动作跳过 staged 直达 applied"""
    action_store = ActionStore(db_session)
    l1_action = await action_store.create_type(ActionTypeCreate(
        name="TouchSeen",
        domain="test",
        params_schema={
            "type": "object",
            "properties": {"object_id": {"type": "integer"}},
            "required": ["object_id"],
        },
        transform=[{"set": "properties.last_seen_marker", "from": "params.object_id"}],
        autonomy_level=1,
        requires_staging=False,
    ))
    sm = StagedStateMachine(db_session)
    bug = await _make_open_bug(db_session, sample_object_type)

    exec = await sm.stage(l1_action.id, {"object_id": bug.id}, "auto_agent")
    assert exec.status == "applied"  # 未 staged，自动应用
    assert exec.applied_at is not None


async def test_full_flow_approve_apply_revert(db_session, sample_object_type, sample_action_type):
    """主流程：stage → approve → apply → 验证生效 → revert → 验证恢复"""
    sm = StagedStateMachine(db_session)
    store = ObjectStore(db_session)
    bug = await _make_open_bug(db_session, sample_object_type, priority=1)

    exec = await sm.stage(
        sample_action_type.id,
        {"object_id": bug.id, "priority": 5},
        "agent", f"{bug.id}-ChangePriority",
    )
    # 审批人看上下文（staged 记录含 before 快照）
    assert exec.exec_log_json["before"]["priority"] == 1

    approved = await sm.approve(exec.id, reviewed_by="reviewer", review_comment="同意")
    assert approved.status == "approved"
    assert approved.reviewed_by == "reviewer"

    applied = await sm.apply(exec.id)
    assert applied.status == "applied"

    updated = await store.get_object(bug.id)
    assert updated.properties["priority"] == 5  # transform 生效

    reverted = await sm.revert(exec.id)
    assert reverted.status == "reverted"
    restored = await store.get_object(bug.id)
    assert restored.properties["priority"] == 1  # 补偿恢复原值


async def test_reject_with_comment(db_session, sample_object_type, sample_action_type):
    sm = StagedStateMachine(db_session)
    bug = await _make_open_bug(db_session, sample_object_type)
    exec = await sm.stage(
        sample_action_type.id, {"object_id": bug.id, "priority": 99},
        "agent", f"{bug.id}-ChangePriority",
    )
    rejected = await sm.reject(exec.id, reviewed_by="reviewer", review_comment="优先级越界")
    assert rejected.status == "rejected"
    assert rejected.review_comment == "优先级越界"

    # rejected 后不能再 approve
    with pytest.raises(ValueError, match="状态"):
        await sm.approve(exec.id, reviewed_by="reviewer")


async def test_invalid_transitions_blocked(db_session, sample_object_type, sample_action_type):
    """非法状态转换被拒（staged 不能直接 apply）"""
    sm = StagedStateMachine(db_session)
    bug = await _make_open_bug(db_session, sample_object_type)
    exec = await sm.stage(
        sample_action_type.id, {"object_id": bug.id, "priority": 2},
        "agent", f"{bug.id}-ChangePriority",
    )
    with pytest.raises(ValueError, match="approved"):
        await sm.apply(exec.id)  # staged → apply 非法


async def test_list_pending(db_session, sample_object_type, sample_action_type):
    sm = StagedStateMachine(db_session)
    bug = await _make_open_bug(db_session, sample_object_type)
    await sm.stage(
        sample_action_type.id, {"object_id": bug.id, "priority": 4},
        "agent", f"{bug.id}-ChangePriority",
    )
    pending = await sm.list_pending()
    assert any(p.id for p in pending)
    assert all(p.status == "staged" for p in pending)


async def test_action_store_upsert_and_dsl_register(db_session):
    """ActionStore upsert + 从 DSL 字典注册"""
    store = ActionStore(db_session)
    created = await store.create_type(ActionTypeCreate(
        name="CreateBug",
        domain="aiqa",
        params_schema={"type": "object", "properties": {"title": {"type": "string"}}, "required": ["title"]},
        autonomy_level=2,
        requires_staging=True,
        description_for_agent="创建 Bug",
    ))
    # 再注册同名 → upsert
    from yuanzhu.ontology.schema import parse_action_type_yaml
    parsed = parse_action_type_yaml("""
name: CreateBug
domain: aiqa
description_for_agent: 创建 Bug（v2 描述）
autonomy_level: 2
params:
  type: object
  properties:
    title: {type: string}
  required: [title]
""")
    updated = await store.register_from_dsl(parsed)
    assert updated.id == created.id
    assert updated.description_for_agent == "创建 Bug（v2 描述）"
