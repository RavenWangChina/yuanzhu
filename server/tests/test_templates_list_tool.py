"""v0.2.2 MCP 工具面补缺：templates_list——纯 MCP 会话可查模板清单

来源：真实使用反馈（Claude 纯 MCP 会话查模板要绕插件源码）。
"""
import pytest
from pathlib import Path

from yuanzhu.main import app
from yuanzhu.db.database import get_db
from yuanzhu.template.store import TemplateStore

DEMO_DIR = Path(__import__("yuanzhu.__init__", fromlist=["__file__"]).__file__).parent / "templates" / "demo"


@pytest.fixture
async def client(db_session):
    async def override():
        yield db_session
    app.dependency_overrides[get_db] = override
    await TemplateStore(db_session).register_dir(DEMO_DIR)
    from httpx import AsyncClient, ASGITransport
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as c:
        yield c
    app.dependency_overrides.clear()


async def test_templates_list_in_tools_list(client):
    """工具清单含 templates_list 且注解齐全（只读）"""
    resp = await client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
    tools = resp.json()["result"]["tools"]
    t = next((x for x in tools if x["name"] == "templates_list"), None)
    assert t, "缺 templates_list 工具"
    ann = t["annotations"]
    assert ann["readOnlyHint"] is True and ann["destructiveHint"] is False


async def test_templates_list_returns_templates(client):
    """调用返回已注册模板（含 demo 域）"""
    resp = await client.post("/mcp", json={"jsonrpc": "2.0", "id": 2, "method": "tools/call",
                                           "params": {"name": "templates_list", "arguments": {}}})
    result = resp.json()["result"]
    assert result.get("isError") is not True
    import json as _json
    data = _json.loads(result["content"][0]["text"])
    names = [t["name"] for t in data["templates"]]
    assert "demo" in names
    demo = next(t for t in data["templates"] if t["name"] == "demo")
    assert demo["status"] == "published"
    assert "workflow_count" in demo


async def test_templates_list_domain_filter(client):
    """按域过滤"""
    resp = await client.post("/mcp", json={"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                                           "params": {"name": "templates_list", "arguments": {"domain": "demo"}}})
    import json as _json
    data = _json.loads(resp.json()["result"]["content"][0]["text"])
    assert all(t["name"] == "demo" for t in data["templates"])
