"""H7 端到端验证测试（技术验证路线 H7 通过标准的可重放脚本）

H7 通过标准：
  agent 经 MCP 查对象 / 执行 staged 动作 / 人审-落库-撤销全通

场景：外部 agent（Claude Code）通过 /mcp 端点与本体层完整交互。
"""
import pytest
from httpx import AsyncClient, ASGITransport

from yuanzhu.main import app
from yuanzhu.db.database import get_db

AGENT_HEADERS = {"X-Agent-ID": "claude-code-external-agent"}


@pytest.fixture
async def client(db_session):
    async def override():
        yield db_session

    app.dependency_overrides[get_db] = override
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


async def _mcp(client: AsyncClient, method: str, params: dict, headers=None) -> dict:
    resp = await client.post("/mcp", json={"method": method, "params": params},
                             headers=headers or AGENT_HEADERS)
    assert resp.status_code == 200
    return resp.json()


async def test_h7_end_to_end(client):
    """H7 主链路：查询 → staged 执行 → 人审 → 落库 → 撤销，全通"""

    # -- 准备：注册 Bug 域（对象类型 exposed + 动作类型）--
    resp = await client.post("/api/objects/types", json={
        "name": "Bug", "domain": "h7", "title_key": "title",
        "description": "H7 验证域的 Bug",
        "properties": {
            "title": {"type": "string", "required": True},
            "status": {"type": "string", "enum": ["Open", "Closed"], "default": "Open"},
            "priority": {"type": "integer"},
        },
        "exposed": True,
    })
    assert resp.status_code == 200
    bug_type_id = resp.json()["id"]

    resp = await client.post("/api/actions/types", json={
        "name": "ChangePriority", "domain": "h7",
        "params_schema": {
            "type": "object",
            "properties": {"object_id": {"type": "integer"}, "priority": {"type": "integer"}},
            "required": ["object_id", "priority"],
        },
        "submission_criteria": {
            "object_ref": "params.object_id",
            "check": {"properties.status": "Open"},
        },
        "transform": [{"set": "properties.priority", "from": "params.priority"}],
        "autonomy_level": 2,
        "requires_staging": True,
        "description_for_agent": "修改 Open 状态 Bug 的优先级",
        "idempotency_key_template": "{object_id}-{name}",
    })
    assert resp.status_code == 200

    # 建一个真实对象
    resp = await client.post("/api/objects", json={
        "type_id": bug_type_id,
        "properties": {"title": "H7-主链路-Bug", "status": "Open", "priority": 1},
        "created_by": "seed",
    })
    obj_id = resp.json()["id"]

    # -- 1. agent 发现工具（MCP 工具自动生成）--
    tools = await _mcp(client, "tools/list", {})
    names = [t["name"] for t in tools["tools"]]
    assert "query_h7_bug" in names
    assert "execute_h7_changepriority" in names
    assert "approve_action" in names and "reject_action" in names

    # -- 2. agent 查对象 --
    result = await _mcp(client, "tools/call", {
        "name": "query_h7_bug", "arguments": {"filter": {"status": "Open"}},
    })
    assert any(o["id"] == obj_id for o in result["objects"])

    # -- 3. agent 执行 staged 动作（写默认人审）--
    result = await _mcp(client, "tools/call", {
        "name": "execute_h7_changepriority",
        "arguments": {"object_id": obj_id, "priority": 5},
    })
    assert result["status"] == "staged"
    exec_id = result["exec_id"]
    assert result["before"]["priority"] == 1  # 审批上下文含 before 快照

    # -- 4. 幂等：agent 重试同请求返回同一 staged 记录 --
    result2 = await _mcp(client, "tools/call", {
        "name": "execute_h7_changepriority",
        "arguments": {"object_id": obj_id, "priority": 5},
    })
    assert result2["exec_id"] == exec_id

    # -- 5. 语义校验：Closed 的 Bug 拒绝 stage --
    await client.post("/api/objects", json={
        "type_id": bug_type_id,
        "properties": {"title": "H7-已关闭", "status": "Closed", "priority": 2},
        "created_by": "seed",
    })
    closed = (await client.get("/api/objects?domain=h7")).json()
    closed_id = next(o["id"] for o in closed if o["properties"]["title"] == "H7-已关闭")
    result = await _mcp(client, "tools/call", {
        "name": "execute_h7_changepriority",
        "arguments": {"object_id": closed_id, "priority": 9},
    })
    assert "error" in result and "submission_criteria" in result["error"]

    # -- 6. 人审批准 → 落库 --
    result = await _mcp(client, "tools/call", {
        "name": "approve_action",
        "arguments": {"exec_id": exec_id, "comment": "H7 验证通过，批准"},
    })
    assert result["status"] == "applied"
    obj = (await client.get(f"/api/objects/{obj_id}")).json()
    assert obj["properties"]["priority"] == 5  # 落库生效

    # -- 7. 撤销（补偿事务）--
    result = await _mcp(client, "tools/call", {
        "name": "reject_action",  # 已 applied 的动作拒绝无效（终态前校验）
        "arguments": {"exec_id": exec_id, "comment": "试错"},
    })
    assert "error" in result  # applied 只能 revert

    resp = await client.post(f"/api/staged/{exec_id}/revert")
    assert resp.json()["status"] == "reverted"
    obj = (await client.get(f"/api/objects/{obj_id}")).json()
    assert obj["properties"]["priority"] == 1  # 补偿恢复

    # -- H7 主链路全通 --


async def test_h7_l1_auto_path(client):
    """H7 旁路：L1 确定性动作自动执行（无需人审）"""
    resp = await client.post("/api/objects/types", json={
        "name": "Task", "domain": "h7auto", "title_key": "name",
        "properties": {"name": {"type": "string", "required": True}, "seen_count": {"type": "integer"}},
    })
    type_id = resp.json()["id"]
    resp = await client.post("/api/objects", json={
        "type_id": type_id, "properties": {"name": "自动任务", "seen_count": 0},
    })
    obj_id = resp.json()["id"]

    resp = await client.post("/api/actions/types", json={
        "name": "MarkSeen", "domain": "h7auto",
        "params_schema": {"type": "object", "properties": {"object_id": {"type": "integer"}}, "required": ["object_id"]},
        "transform": [{"set": "properties.seen_count", "value": 1}],
        "autonomy_level": 1,
        "requires_staging": False,
    })
    assert resp.status_code == 200

    result = await _mcp(client, "tools/call", {
        "name": "execute_h7auto_markseen", "arguments": {"object_id": obj_id},
    })
    assert result["status"] == "applied"  # L1 自动执行
    obj = (await client.get(f"/api/objects/{obj_id}")).json()
    assert obj["properties"]["seen_count"] == 1
