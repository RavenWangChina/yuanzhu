"""v0.2.0 安装硬化：litellm 可选化——OpenAI 兼容端点走零依赖直连层

核心断言：
- api_base 存在且模型无 litellm 特殊前缀 → 直连（不 import litellm）
- 直连响应与 litellm 响应在 call_model/extract_usage 处同构兼容
- litellm 特殊前缀模型且未装 litellm → 友好安装提示
- litellm 已装时行为不变（回归）
"""
import pytest
import sys

import yuanzhu.gateway.proxy as proxy


@pytest.fixture
def no_litellm(monkeypatch):
    """模拟 litellm 未安装（从 sys.modules 摘除）"""
    saved = sys.modules.pop("litellm", None)
    monkeypatch.setattr(sys, "modules", {**sys.modules, "litellm": None})  # None 触发 ImportError
    yield
    if saved is not None:
        sys.modules["litellm"] = saved


async def test_openai_direct_used_when_api_base(db_session, monkeypatch):
    """api_base + 无 litellm 前缀 → 走直连层（不碰 litellm）"""
    calls = {}

    class FakeResp:
        def raise_for_status(self): pass
        def json(self):
            return {"choices": [{"message": {"content": "直连回复"}}],
                    "usage": {"prompt_tokens": 5, "completion_tokens": 3}}

    class FakeClient:
        def __init__(self, **kw): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def post(self, url, **kw):
            calls["url"] = url
            calls["json"] = kw.get("json")
            calls["headers"] = kw.get("headers")
            return FakeResp()

    import httpx
    monkeypatch.setattr(httpx, "AsyncClient", FakeClient)

    resp = await proxy.acompletion(
        model="glm-5.1",
        messages=[{"role": "user", "content": "hi"}],
    )
    assert resp["choices"][0]["message"]["content"] == "直连回复"
    assert "/chat/completions" in calls["url"]
    assert calls["json"]["model"] == "glm-5.1"


async def test_openai_direct_used_without_litellm(db_session, monkeypatch, no_litellm):
    """litellm 未安装时：OpenAI 兼容端点依旧可用（核心场景）"""

    class FakeResp:
        def raise_for_status(self): pass
        def json(self):
            return {"choices": [{"message": {"content": "ok"}}], "usage": {}}

    class FakeClient:
        def __init__(self, **kw): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def post(self, url, **kw): return FakeResp()

    import httpx
    monkeypatch.setattr(httpx, "AsyncClient", FakeClient)
    resp = await proxy.acompletion(model="glm-5.1", messages=[{"role": "user", "content": "x"}])
    assert resp["choices"][0]["message"]["content"] == "ok"


async def test_litellm_needed_but_missing_gives_hint(db_session, monkeypatch, no_litellm):
    """litellm 特殊前缀模型 + 未装 → 友好安装提示"""
    with pytest.raises(ValueError) as ei:
        await proxy.acompletion(model="anthropic/claude-x", messages=[{"role": "user", "content": "x"}])
    assert "yuanzhu[gateway]" in str(ei.value)


async def test_extract_usage_accepts_direct_dict(db_session):
    """直连层返回的 dict 与 extract_usage 兼容"""
    usage = proxy.extract_usage({"choices": [], "usage": {"prompt_tokens": 7, "completion_tokens": 2}})
    assert usage == {"prompt_tokens": 7, "completion_tokens": 2}
