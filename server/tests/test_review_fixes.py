"""审查修复测试：C1 JSON突变丢失 / C2 路径穿越 / C3 并发审批 / I1 TOCTOU / I3 注册白名单"""
import pytest
from httpx import AsyncClient, ASGITransport
from pathlib import Path

from yuanzhu.main import app
from yuanzhu.db.database import get_db
from yuanzhu.staged.state_machine import StagedStateMachine
from yuanzhu.ontology.object_store import ObjectStore
from yuanzhu.ontology.action_store import ActionStore
from yuanzhu.models.object import ObjectCreate, ObjectTypeCreate
from yuanzhu.models.action import ActionTypeCreate
from yuanzhu.db import models

AIQA_DIR = Path(__file__).resolve().parents[2] / "templates" / "aiqa"


async def _make_bug(db_session, sample_object_type, title="X", priority=1, status="Open"):
    store = ObjectStore(db_session)
    return await store.create_object(ObjectCreate(
        type_id=sample_object_type.id,
        properties={"title": title, "status": status, "priority": priority},
    ))


# ---------- C1：set 动作的 exec_log 突变必须持久化 ----------

async def test_c1_set_action_log_persisted(db_session, sample_object_type, sample_action_type):
    """set 类动作 apply 后 transform_log/before 必须落库（same-ref 赋值曾不触发 UPDATE）"""
    sm = StagedStateMachine(db_session)
    bug = await _make_bug(db_session, sample_object_type, priority=1)

    exec = await sm.stage(sample_action_type.id, {"object_id": bug.id, "priority": 5}, "a", f"{bug.id}-k")
    exec_id = exec.id
    await sm.approve(exec_id, reviewed_by="r")
    await sm.apply(exec_id)
    await db_session.commit()   # 真实提交（变更检测的关键验证点）

    fresh = await db_session.get(models.ActionExec, exec_id)
    assert fresh.exec_log_json is not None
    assert "before" in fresh.exec_log_json, "before 快照丢失（C1 复现）"
    assert fresh.exec_log_json.get("transform_log"), "transform_log 丢失（C1 复现）"


async def test_c1_mixed_action_revert_deletes(db_session, sample_object_type):
    """set+create 混合动作 revert：对象必须删除（created_object_ids 曾不持久化）"""
    action_store = ActionStore(db_session)
    action = await action_store.create_type(ActionTypeCreate(
        name="MixedAction",
        domain="test",
        params_schema={"type": "object", "properties": {"object_id": {"type": "integer"}, "t": {"type": "string"}}},
        transform=[
            {"set": "properties.priority", "value": 9},                       # 先有 set（产生非空 before）
            {"create_object": {"type": "Bug"}, "with": {"title": "from:params.t"}},
        ],
    ))
    bug = await _make_bug(db_session, sample_object_type)
    obj_store = ObjectStore(db_session)
    before_count = len(await obj_store.list_objects(type_id=sample_object_type.id))

    sm = StagedStateMachine(db_session)
    exec = await sm.stage(action.id, {"object_id": bug.id, "t": "混合产物"}, "a")
    await sm.approve(exec.id, reviewed_by="r")
    await sm.apply(exec.id)
    await db_session.commit()

    after_apply = len(await obj_store.list_objects(type_id=sample_object_type.id))
    assert after_apply == before_count + 1

    await sm.revert(exec.id)
    await db_session.commit()
    after_revert = len(await obj_store.list_objects(type_id=sample_object_type.id))
    assert after_revert == before_count, "revert 后对象未删除（C1 复现：created_object_ids 曾丢失）"


# ---------- C2：SPA fallback 路径穿越 ----------

async def test_c2_path_traversal_blocked(db_session):
    async def override():
        yield db_session
    app.dependency_overrides[get_db] = override
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://t") as c:
            for evil in ["/%2e%2e/pyproject.toml", "/..%2f..%2fpyproject.toml", "/%2e%2e%2e%2e/server/.env"]:
                resp = await c.get(evil)
                body = resp.text
                assert "requires-python" not in body and "wecom_aes_key" not in body, \
                    f"路径穿越成功: {evil}"
            # 正常 SPA 路径不受影响
            resp = await c.get("/staged")
            assert resp.status_code == 200
    finally:
        app.dependency_overrides.clear()


# ---------- C3：并发审批乐观锁 ----------

async def test_c3_double_approve_rejected(db_session, sample_object_type, sample_action_type):
    """同一动作被两个审批人并发处理：第二个必须失败（重复执行曾产生双对象）"""
    sm = StagedStateMachine(db_session)
    bug = await _make_bug(db_session, sample_object_type)
    exec = await sm.stage(sample_action_type.id, {"object_id": bug.id, "priority": 7}, "a", f"{bug.id}-k2")

    # 审批人 1：完整走 approve+apply
    await sm.approve(exec.id, reviewed_by="r1")
    applied1 = await sm.apply(exec.id)

    # 审批人 2：并发再 approve（DB 已非 staged → 乐观锁必须拦住）
    with pytest.raises(ValueError, match="已被处理"):
        await sm.approve(exec.id, reviewed_by="r2")
    # 并发再 apply（DB 已 applied → 拦住，防重复执行）
    with pytest.raises(ValueError, match="不可应用"):
        await sm.apply(exec.id)

    assert applied1.status == "applied"


# ---------- I1：apply 复查 submission_criteria（TOCTOU） ----------

async def test_i1_criteria_rechecked_on_apply(db_session, sample_object_type, sample_action_type):
    """stage 时 Open、审批等待期变 Closed → apply 必须拒绝（不能按失真上下文执行）"""
    sm = StagedStateMachine(db_session)
    bug = await _make_bug(db_session, sample_object_type, status="Open")
    exec = await sm.stage(sample_action_type.id, {"object_id": bug.id, "priority": 4}, "a", f"{bug.id}-k3")
    await sm.approve(exec.id, reviewed_by="r")

    # 等待期间对象被关闭
    bug.properties_json["status"] = "Closed"
    await db_session.flush()

    with pytest.raises(ValueError, match="submission_criteria"):
        await sm.apply(exec.id)


# ---------- I3：模板注册路径白名单 ----------

async def test_i3_register_path_whitelisted(db_session, tmp_path):
    """注册路径必须在服务端 templates/ 根之下（任意目录注册曾可注入动作+MCP 执行面）"""
    import json as _json
    async def override():
        yield db_session
    app.dependency_overrides[get_db] = override
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://t") as c:
            # 临时目录（白名单外）——即使结构合法也拒绝
            (tmp_path / "manifest.yaml").write_text(
                "name: evil\nversion: 0.1\ndomain: evil\n", encoding="utf-8")
            resp = await c.post("/api/templates/register", json={"path": str(tmp_path)})
            assert resp.status_code == 400
            assert "白名单" in resp.json()["detail"] or "templates" in resp.json()["detail"]

            # 白名单内（真实 aiqa 模板）正常
            resp = await c.post("/api/templates/register", json={"path": str(AIQA_DIR)})
            assert resp.status_code == 200, resp.json()
    finally:
        app.dependency_overrides.clear()


# ---------- M1：wecom 配了 key 必须 fail-closed ----------

async def test_m1_wecom_key_fail_closed(db_session, monkeypatch):
    from yuanzhu.config import settings
    monkeypatch.setattr(settings, "wecom_aes_key", "some-key-123")
    async def override():
        yield db_session
    app.dependency_overrides[get_db] = override
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://t") as c:
            resp = await c.get("/api/dialog/wecom/callback", params={"echostr": "x"})
            assert resp.status_code == 503, "配了 AES key 但验签未实现时必须拒绝（fail-closed）"
    finally:
        app.dependency_overrides.clear()
