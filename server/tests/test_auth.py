"""Bearer 认证中间件测试（审查 I5 修复；未配 token=零摩擦本机模式）"""
import pytest
from httpx import AsyncClient, ASGITransport

from yuanzhu.main import app
from yuanzhu.db.database import get_db


def mcp_call_payload(method: str, params: dict | None = None, req_id: int = 1) -> dict:
    """标准 MCP JSON-RPC 请求体"""
    return {"jsonrpc": "2.0", "id": req_id, "method": method, "params": params or {}}


def mcp_unpack(resp_json: dict) -> dict:
    """解开 tools/call result.content[0].text"""
    import json as _json
    content = (resp_json or {}).get("result", {}).get("content", [])
    return _json.loads(content[0].get("text", "{}")) if content else {}



async def _client(db_session, headers=None):
    async def override():
        yield db_session
    app.dependency_overrides[get_db] = override
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://t", headers=headers or {})


async def test_no_token_configured_open(db_session):
    """未配 YUANZHU_API_TOKEN：一切如常（本机零摩擦）"""
    from yuanzhu.config import settings
    import yuanzhu.main as main_mod
    saved = settings.api_token
    settings.api_token = ""
    main_mod._auth_singleton = None  # 重置中间件缓存
    try:
        async with await _client(db_session) as c:
            assert (await c.get("/health")).status_code == 200
            assert (await c.get("/api/staged/pending")).status_code == 200
    finally:
        settings.api_token = saved
        main_mod._auth_singleton = None


async def test_token_required_when_configured(db_session, monkeypatch):
    """配了 token：无/错 token → 401；对 token → 200"""
    from yuanzhu.config import settings
    import yuanzhu.main as main_mod
    monkeypatch.setattr(settings, "api_token", "sec-123")
    main_mod._auth_singleton = None
    try:
        async with await _client(db_session) as c:
            assert (await c.get("/api/staged/pending")).status_code == 401
            r = await c.get("/api/staged/pending",
                            headers={"Authorization": "Bearer wrong"})
            assert r.status_code == 401
            r = await c.get("/api/staged/pending",
                            headers={"Authorization": "Bearer sec-123"})
            assert r.status_code == 200
    finally:
        main_mod._auth_singleton = None


async def test_exempt_paths(db_session, monkeypatch):
    """豁免：/health（存活探测）与静态资源（Web 壳可打开；API 仍拦截）"""
    from yuanzhu.config import settings
    import yuanzhu.main as main_mod
    monkeypatch.setattr(settings, "api_token", "sec-123")
    main_mod._auth_singleton = None
    try:
        async with await _client(db_session) as c:
            assert (await c.get("/health")).status_code == 200
            # SPA 兜底（index.html）可打开——登录壳要先能显示
            r = await c.get("/")
            assert r.status_code == 200 and "元铸工坊" in r.text
            # API 仍拦
            assert (await c.get("/api/nodes")).status_code == 401
            assert (await c.get("/api/usage")).status_code == 401
    finally:
        main_mod._auth_singleton = None


async def test_mcp_requires_token(db_session, monkeypatch):
    """MCP 端点同拦（X-Agent-ID 是标识不是认证）"""
    from yuanzhu.config import settings
    import yuanzhu.main as main_mod
    monkeypatch.setattr(settings, "api_token", "sec-123")
    main_mod._auth_singleton = None
    try:
        async with await _client(db_session) as c:
            r = await c.post("/mcp", json=mcp_call_payload("tools/list"))
            assert r.status_code == 401
            r = await c.post("/mcp", json=mcp_call_payload("tools/list"),
                             headers={"Authorization": "Bearer sec-123",
                                      "X-Agent-ID": "agent"})
            assert r.status_code == 200
    finally:
        main_mod._auth_singleton = None
