"""LiteLLM 网关测试（ADR-003：OpenAI 兼容端点 + 计量落库）

litellm.acompletion 被 mock——测试网关的转发/计量/降级逻辑，不打真实供应商。
"""
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


async def _fake_completion(**kwargs):
    """litellm.acompletion 的替身：返回带 usage 的响应"""
    class Resp:
        def model_dump(self):
            return {
                "id": "cmpl-fake",
                "object": "chat.completion",
                "model": kwargs.get("model", "test"),
                "choices": [{"message": {"role": "assistant", "content": "模拟回复"}}],
                "usage": {"prompt_tokens": 12, "completion_tokens": 8, "total_tokens": 20},
            }
    return Resp()


async def test_chat_completions_proxied_and_metered(client, monkeypatch):
    from yuanzhu.gateway import router as gateway
    monkeypatch.setattr("yuanzhu.gateway.proxy.litellm.acompletion", _fake_completion)

    resp = await client.post("/v1/chat/completions", json={
        "model": "deepseek-chat",
        "messages": [{"role": "user", "content": "你好"}],
        "metadata": {"task_id": 42, "caller": "ai-step"},
    }, headers={"X-Node-Token": "tok-meter"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["choices"][0]["message"]["content"] == "模拟回复"
    assert data["usage"]["total_tokens"] == 20


async def test_usage_recorded(client, db_session, monkeypatch):
    """计量落库：谁/任务/模型/token"""
    monkeypatch.setattr("yuanzhu.gateway.proxy.litellm.acompletion", _fake_completion)

    await client.post("/v1/chat/completions", json={
        "model": "deepseek-chat",
        "messages": [{"role": "user", "content": "hi"}],
        "metadata": {"task_id": 42, "caller": "ai-step"},
    })

    from sqlalchemy import select
    from yuanzhu.db.models import ModelUsage
    result = await db_session.execute(select(ModelUsage))
    usages = list(result.scalars().all())
    assert len(usages) == 1
    u = usages[0]
    assert u.model == "deepseek-chat"
    assert u.task_id == 42
    assert u.caller == "ai-step"
    assert u.prompt_tokens == 12
    assert u.completion_tokens == 8
    assert u.estimated_cost is not None  # 估费可算（可为 0）


async def test_models_endpoint(client):
    resp = await client.get("/v1/models")
    assert resp.status_code == 200
    ids = [m["id"] for m in resp.json()["data"]]
    assert "deepseek-chat" in ids


async def test_gateway_error_returns_502(client, monkeypatch):
    """供应商异常 → 502 + 附上下文（降级兜底带上下文，DMLA）"""
    async def boom(**kwargs):
        raise RuntimeError("供应商超时")

    monkeypatch.setattr("yuanzhu.gateway.proxy.litellm.acompletion", boom)
    resp = await client.post("/v1/chat/completions", json={
        "model": "deepseek-chat",
        "messages": [{"role": "user", "content": "x"}],
    })
    assert resp.status_code == 502
    assert "deepseek-chat" in resp.json()["detail"]  # 错误附模型上下文
