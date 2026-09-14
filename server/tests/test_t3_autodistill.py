"""T3 采纳即沉淀：approve metaflow/SaveAnswer → 自动产生洞见候选（staged）"""
import pytest
from pathlib import Path

from yuanzhu.main import app
from yuanzhu.db.database import get_db
from yuanzhu.template.store import TemplateStore


def mcp_call_payload(method: str, params: dict | None = None, req_id: int = 1) -> dict:
    """标准 MCP JSON-RPC 请求体"""
    return {"jsonrpc": "2.0", "id": req_id, "method": method, "params": params or {}}


def mcp_unpack(resp_json: dict) -> dict:
    """解开 tools/call result.content[0].text"""
    import json as _json
    content = (resp_json or {}).get("result", {}).get("content", [])
    return _json.loads(content[0].get("text", "{}")) if content else {}


METAFLOW_DIR = Path(__import__("yuanzhu.__init__", fromlist=["__file__"]).__file__).parent / "templates" / "metaflow"


@pytest.fixture
async def client(db_session, monkeypatch):
    async def override():
        yield db_session
    app.dependency_overrides[get_db] = override

    # distill 的 AI 调用 mock（返回 1 条洞见）
    import yuanzhu.workflow.engine as engine_mod
    async def fake_chat(model, prompt, session=None, **kw):
        return '[{"takeaway": "20人以下团队优先托管", "context": "团队规模判断"}]'
    monkeypatch.setattr(engine_mod, "call_model", fake_chat)

    # T3 用独立 session 跑 distill——mock 的 session 参数透传 OK
    await TemplateStore(db_session).register_dir(METAFLOW_DIR)

    from httpx import AsyncClient, ASGITransport
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as c:
        yield c
    app.dependency_overrides.clear()


async def test_saveanswer_is_l1_autoapplied(client, db_session):
    """v0.1.3 语义：SaveAnswer 是 L1——答案自动入库（不点采纳也可用），
    采纳与沉淀链路由 test_autosave 的 adopt 用例覆盖"""
    resp = await client.post("/mcp", json=mcp_call_payload("tools/call", {
        "name": "execute_metaflow_saveanswer",
        "arguments": {"question": "该不该自建中台",
                      "content": "【结论】分情况…"}}), headers={"X-Agent-ID": "t"})
    assert resp.status_code == 200
    assert mcp_unpack(resp.json())["status"] == "applied", "SaveAnswer 应为 L1 自动入库"
