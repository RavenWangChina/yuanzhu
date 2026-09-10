"""节点/任务/模板 REST API 测试（dsh-edge 与控制台的前置接口）"""
import pytest
from httpx import AsyncClient, ASGITransport
from pathlib import Path

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


# ---------- 节点 ----------

async def test_node_register_and_heartbeat(client):
    resp = await client.post("/api/nodes/register", json={
        "name": "edge-a", "token": "tok-a",
        "capabilities": {"os": "windows", "dsh": True},
    })
    assert resp.status_code == 200
    node_id = resp.json()["id"]
    assert resp.json()["status"] == "online"

    resp = await client.post(f"/api/nodes/{node_id}/heartbeat", json={
        "status": "busy", "current_task_id": 7,
        "resource_usage": {"cpu": 30.0},
    })
    assert resp.json()["status"] == "busy"

    resp = await client.get("/api/nodes")
    assert any(n["id"] == node_id for n in resp.json())


async def test_node_pull_tasks(client):
    """dsh-edge 主路径：注册 → 建任务 → 分发 → pull 拿到 running 任务"""
    resp = await client.post("/api/nodes/register", json={
        "name": "edge-b", "token": "tok-b", "capabilities": {"dsh": True},
    })
    node_id = resp.json()["id"]

    resp = await client.post("/api/tasks", json={
        "params": {"workflow": "demo"}, "created_by": "web-user",
    })
    task_id = resp.json()["id"]
    assert resp.json()["status"] == "pending"

    resp = await client.post(f"/api/tasks/{task_id}/dispatch/{node_id}")
    assert resp.json()["status"] == "dispatched"

    resp = await client.post(f"/api/nodes/{node_id}/tasks/pull")
    pulled = resp.json()
    assert len(pulled) == 1
    assert pulled[0]["status"] == "running"

    # 回报完成
    resp = await client.post(f"/api/tasks/{task_id}/report", json={
        "status": "done", "result": {"output": "ok"},
    })
    assert resp.json()["status"] == "done"
    assert resp.json()["result"] == {"output": "ok"}


# ---------- 任务 ----------

async def test_task_list_and_detail(client):
    resp = await client.post("/api/tasks", json={"params": {"k": 1}, "created_by": "u"})
    task_id = resp.json()["id"]

    resp = await client.get("/api/tasks?created_by=u")
    assert any(t["id"] == task_id for t in resp.json())

    resp = await client.get(f"/api/tasks/{task_id}")
    assert resp.json()["id"] == task_id

    resp = await client.get("/api/tasks/99999")
    assert resp.status_code == 404


# ---------- 模板 ----------

async def test_template_register_and_list(client, tmp_path):
    """模板注册 API（上传目录形态 v0.1 用本地路径，zip 上传留后续）"""
    (tmp_path / "manifest.yaml").write_text(
        "name: mini\nversion: 0.1.0\ndomain: mini\n", encoding="utf-8")
    (tmp_path / "ontology").mkdir()
    (tmp_path / "ontology" / "object-types.yaml").write_text(
        "types:\n  - name: Item\n    properties:\n      name: {type: string, required: true}\n",
        encoding="utf-8")

    resp = await client.post("/api/templates/register", json={"path": str(tmp_path)})
    assert resp.status_code == 200
    assert resp.json()["name"] == "mini"
    assert resp.json()["status"] == "published"

    resp = await client.get("/api/templates")
    assert any(t["name"] == "mini" for t in resp.json())

    # 幂等
    resp = await client.post("/api/templates/register", json={"path": str(tmp_path)})
    assert resp.status_code == 200
    resp = await client.get("/api/templates?domain=mini")
    assert len(resp.json()) == 1
