"""REST API 测试：对象/动作/审批端点（待审中心的后端）"""
import pytest
from httpx import AsyncClient, ASGITransport

from yuanzhu.main import app
from yuanzhu.db.database import get_db


@pytest.fixture
async def client(db_session):
    async def override():
        yield db_session

    app.dependency_overrides[get_db] = override
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


async def test_health(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


async def test_object_type_crud(client):
    # 创建类型
    resp = await client.post("/api/objects/types", json={
        "name": "TestCase",
        "domain": "api",
        "title_key": "name",
        "properties": {"name": {"type": "string", "required": True}},
        "exposed": True,
    })
    assert resp.status_code == 200
    type_id = resp.json()["id"]

    # 再创建同名（upsert 不报错）
    resp2 = await client.post("/api/objects/types", json={
        "name": "TestCase", "domain": "api",
        "properties": {"name": {"type": "string", "required": True}},
    })
    assert resp2.json()["id"] == type_id

    # 列出类型
    resp = await client.get("/api/objects/types?domain=api")
    assert any(t["id"] == type_id for t in resp.json())


async def test_object_crud(client):
    resp = await client.post("/api/objects/types", json={
        "name": "Bug", "domain": "api", "title_key": "title",
        "properties": {
            "title": {"type": "string", "required": True},
            "status": {"type": "string", "enum": ["Open", "Closed"], "default": "Open"},
        },
    })
    type_id = resp.json()["id"]

    # 创建对象
    resp = await client.post("/api/objects", json={
        "type_id": type_id,
        "properties": {"title": "API Bug", "status": "Open"},
        "created_by": "tester",
    })
    assert resp.status_code == 200
    obj_id = resp.json()["id"]
    assert resp.json()["title"] == "API Bug"

    # 查单个
    resp = await client.get(f"/api/objects/{obj_id}")
    assert resp.status_code == 200

    # 列表
    resp = await client.get("/api/objects?domain=api")
    assert len(resp.json()) >= 1

    # 404
    resp = await client.get("/api/objects/99999")
    assert resp.status_code == 404

    # 校验失败 → 400
    resp = await client.post("/api/objects", json={
        "type_id": type_id, "properties": {"status": "Open"},  # 缺 title
    })
    assert resp.status_code == 400


async def test_staged_approval_flow(client):
    """审批全流程：建类型/对象/动作 → stage → pending → approve → 生效 → revert"""
    # 类型+对象
    resp = await client.post("/api/objects/types", json={
        "name": "Bug", "domain": "flow", "title_key": "title",
        "properties": {"title": {"type": "string", "required": True}, "priority": {"type": "integer"}},
    })
    type_id = resp.json()["id"]
    resp = await client.post("/api/objects", json={
        "type_id": type_id, "properties": {"title": "审批流 Bug", "priority": 1},
    })
    obj_id = resp.json()["id"]

    # 动作
    resp = await client.post("/api/actions/types", json={
        "name": "ChangePriority", "domain": "flow",
        "params_schema": {
            "type": "object",
            "properties": {"object_id": {"type": "integer"}, "priority": {"type": "integer"}},
            "required": ["object_id", "priority"],
        },
        "transform": [{"set": "properties.priority", "from": "params.priority"}],
        "autonomy_level": 2,
        "requires_staging": True,
    })
    action_id = resp.json()["id"]

    # stage（写操作默认 staged）
    resp = await client.post("/api/actions/execute", json={
        "action_type_id": action_id,
        "params": {"object_id": obj_id, "priority": 9},
        "staged_by": "api_agent",
    })
    assert resp.status_code == 200
    exec_id = resp.json()["id"]
    assert resp.json()["status"] == "staged"

    # pending 列表
    resp = await client.get("/api/staged/pending")
    assert any(p["id"] == exec_id for p in resp.json())

    # 批准（自动应用）
    resp = await client.post(f"/api/staged/{exec_id}/approve", json={
        "reviewed_by": "human_reviewer", "review_comment": "通过",
    })
    assert resp.status_code == 200
    assert resp.json()["status"] == "applied"

    # 对象已生效
    resp = await client.get(f"/api/objects/{obj_id}")
    assert resp.json()["properties"]["priority"] == 9

    # 撤销恢复
    resp = await client.post(f"/api/staged/{exec_id}/revert")
    assert resp.json()["status"] == "reverted"
    resp = await client.get(f"/api/objects/{obj_id}")
    assert resp.json()["properties"]["priority"] == 1


async def test_staged_reject_flow(client):
    resp = await client.post("/api/objects/types", json={
        "name": "Bug", "domain": "rej", "title_key": "title",
        "properties": {"title": {"type": "string", "required": True}},
    })
    type_id = resp.json()["id"]
    resp = await client.post("/api/objects", json={
        "type_id": type_id, "properties": {"title": "拒绝流"},
    })
    obj_id = resp.json()["id"]
    resp = await client.post("/api/actions/types", json={
        "name": "Noop", "domain": "rej",
        "params_schema": {"type": "object", "properties": {"object_id": {"type": "integer"}}},
    })
    action_id = resp.json()["id"]

    resp = await client.post("/api/actions/execute", json={
        "action_type_id": action_id, "params": {"object_id": obj_id}, "staged_by": "a",
    })
    exec_id = resp.json()["id"]

    # 拒绝（必须带理由；缺 comment 被 schema 拦截，FastAPI 422）
    resp = await client.post(f"/api/staged/{exec_id}/reject", json={"reviewed_by": "r"})
    assert resp.status_code == 422

    resp = await client.post(f"/api/staged/{exec_id}/reject", json={
        "reviewed_by": "r", "review_comment": "不需要",
    })
    assert resp.json()["status"] == "rejected"
