"""MCP 工具生成器 + Streamable HTTP 服务端测试"""
import pytest
from httpx import AsyncClient, ASGITransport

from yuanzhu.main import app
from yuanzhu.mcp.tools import MCPToolGenerator
from yuanzhu.ontology.object_store import ObjectStore
from yuanzhu.ontology.action_store import ActionStore
from yuanzhu.models.object import ObjectTypeCreate, ObjectCreate
from yuanzhu.models.action import ActionTypeCreate


# ---------- 工具生成 ----------

async def test_generate_query_tool(db_session, sample_object_type):
    gen = MCPToolGenerator(db_session)
    tool = await gen.generate_query_tool(sample_object_type.id)
    assert tool["name"] == "query_test_bug"  # query_{domain}_{name} 小写
    assert "inputSchema" in tool


async def test_generate_query_tool_unexposed_returns_none(db_session, sample_object_type):
    """exposed=False 的类型不生成工具（最小权限）"""
    sample_object_type.exposed = False
    await db_session.flush()
    gen = MCPToolGenerator(db_session)
    assert await gen.generate_query_tool(sample_object_type.id) is None


async def test_generate_action_tool_marks_staging(db_session, sample_action_type):
    gen = MCPToolGenerator(db_session)
    tool = await gen.generate_action_tool(sample_action_type.id)
    assert tool["name"] == "execute_test_changepriority"
    assert "（需要审批）" in tool["description"]  # requires_staging 标注
    assert tool["description"].startswith("修改 Bug 优先级")  # description_for_agent


async def test_list_tools_includes_approval_tools(db_session):
    gen = MCPToolGenerator(db_session)
    tools = await gen.list_tools()
    names = [t["name"] for t in tools]
    assert "list_pending_approvals" in names
    assert "approve_action" in names
    assert "reject_action" in names


# ---------- HTTP 服务端 ----------

@pytest.fixture
async def client(db_session):
    """MCP HTTP 客户端：dependency_overrides 把 get_db 指到测试内存库"""
    from yuanzhu.db.database import get_db

    async def override():
        yield db_session

    app.dependency_overrides[get_db] = override
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


async def test_mcp_tools_list(client):
    resp = await client.post("/mcp", json={"method": "tools/list", "params": {}})
    assert resp.status_code == 200
    names = [t["name"] for t in resp.json()["tools"]]
    assert "list_pending_approvals" in names


async def test_mcp_query_objects_flow(client, db_session, sample_object_type):
    """MCP 查询对象（H7 验证链第一环）"""
    store = ObjectStore(db_session)
    await store.create_object(ObjectCreate(
        type_id=sample_object_type.id,
        properties={"title": "MCP 查的 Bug", "status": "Open"},
    ))
    resp = await client.post("/mcp", json={
        "method": "tools/call",
        "params": {"name": "query_test_bug", "arguments": {"filter": {"status": "Open"}}},
    })
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["objects"]) >= 1
    assert data["objects"][0]["properties"]["title"] == "MCP 查的 Bug"


async def test_mcp_execute_action_stages(client, db_session, sample_object_type, sample_action_type):
    """MCP 执行 staged 动作（H7 第二环）：返回 staged 状态+exec_id"""
    store = ObjectStore(db_session)
    bug = await store.create_object(ObjectCreate(
        type_id=sample_object_type.id,
        properties={"title": "MCP Bug", "status": "Open", "priority": 1},
    ))
    resp = await client.post("/mcp", json={
        "method": "tools/call",
        "params": {
            "name": "execute_test_changepriority",
            "arguments": {"object_id": bug.id, "priority": 5},
        },
    }, headers={"X-Agent-ID": "claude-code-agent"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "staged"
    assert "exec_id" in data
    assert "待" in data["message"]


async def test_mcp_query_filters(db_session, sample_object_type, client):
    """filter 过滤：status=Closed 的不返回"""
    store = ObjectStore(db_session)
    await store.create_object(ObjectCreate(
        type_id=sample_object_type.id, properties={"title": "开", "status": "Open"},
    ))
    await store.create_object(ObjectCreate(
        type_id=sample_object_type.id, properties={"title": "关", "status": "Closed"},
    ))
    resp = await client.post("/mcp", json={
        "method": "tools/call",
        "params": {"name": "query_test_bug", "arguments": {"filter": {"status": "Open"}}},
    })
    titles = [o["properties"]["title"] for o in resp.json()["objects"]]
    assert "开" in titles and "关" not in titles


async def test_mcp_unknown_tool(client):
    resp = await client.post("/mcp", json={
        "method": "tools/call", "params": {"name": "no_such_tool", "arguments": {}},
    })
    assert "error" in resp.json()
