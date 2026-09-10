"""对话学习采集测试（spec 3.3：企微回调 → 缓冲 → 提炼 job → 候选进草稿区）

合规断言：消息原文只进内存缓冲，绝不落库（DB 中无消息表/消息字段）。
模型调用 mock。
"""
import pytest
from httpx import AsyncClient, ASGITransport

from yuanzhu.main import app
from yuanzhu.db.database import get_db


@pytest.fixture
async def client(db_session, monkeypatch):
    async def override():
        yield db_session

    app.dependency_overrides[get_db] = override

    # 提炼 job 的模型调用 mock
    import yuanzhu.dialog.refinement as ref_mod
    async def fake_llm(prompt: str, **kwargs) -> str:
        return """[
          {"name": "每日站会纪要", "description": "群内高频：张三每天早9点要昨日测试进展汇总",
           "trigger": "每日 09:00", "steps_draft": ["查询昨日 Bug 变更", "AI 汇总成纪要", "发回群"],
           "layer": "协同层"},
          {"name": "缺陷分诊", "description": "测试多次贴报错截图求分诊",
           "trigger": "消息含截图+报错", "steps_draft": ["AI 读图识别错误", "建 Bug 候选(staged)"],
           "layer": "协同层"}
        ]"""
    monkeypatch.setattr(ref_mod, "call_model", fake_llm)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


async def test_callback_verify_get(client):
    """企微回调 URL 验证（GET echostr 回显；v0.1 明文模式直接回显）"""
    resp = await client.get("/api/dialog/wecom/callback", params={
        "msg_signature": "sig", "timestamp": "123", "nonce": "n", "echostr": "echo-me-123",
    })
    assert resp.status_code == 200
    assert resp.text == "echo-me-123"


async def test_callback_receives_messages(client):
    """POST 收消息进内存缓冲；原文不落库"""
    from yuanzhu.dialog.buffer import message_buffer
    message_buffer.clear()

    for i in range(3):
        resp = await client.post("/api/dialog/wecom/callback", json={
            "from": {"name": "张三", "user_id": "u1"},
            "chat": {"chat_id": "group-a", "name": "测试部日常"},
            "msgtype": "text",
            "text": {"content": f"帮忙看下这个报错 {i}"},
            "timestamp": 1789000000 + i,
        })
        assert resp.status_code == 200

    snapshot = message_buffer.recent()
    assert len(snapshot) == 3
    assert snapshot[0]["text"]["content"].startswith("帮忙看下")


async def test_buffer_bounded(client):
    """缓冲环形上限（内存保护）"""
    from yuanzhu.dialog.buffer import message_buffer
    message_buffer.clear()
    for i in range(message_buffer.maxlen + 20):
        message_buffer.push({"text": {"content": str(i)}, "timestamp": i})
    assert len(message_buffer) == message_buffer.maxlen


async def test_refine_produces_draft_candidates(client, db_session):
    """提炼 job：调模型 → 候选写入 Template 草稿区（status=draft）"""
    from yuanzhu.dialog.buffer import message_buffer
    message_buffer.clear()
    for i in range(5):
        message_buffer.push({
            "from": {"name": "张三", "user_id": "u1"},
            "chat": {"chat_id": "g1", "name": "测试部"},
            "msgtype": "text",
            "text": {"content": f"昨日测试进展怎么样 {i}"},
            "timestamp": 1789000000 + i,
        })

    resp = await client.post("/api/dialog/refine", json={
        "min_messages": 3, "source": "group-a",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["candidates"] == 2

    # 草稿区（模板市场可见 draft 徽章）
    resp = await client.get("/api/templates?status=draft")
    drafts = resp.json()
    assert len(drafts) == 2
    assert any(d["name"] == "每日站会纪要" for d in drafts)
    assert all(d["status"] == "draft" for d in drafts)

    # 诚实边界：候选标注协同层
    import json as j
    manifest = drafts[0]["manifest_json"]
    assert manifest.get("layer") == "协同层"


async def test_refine_requires_enough_messages(client):
    """消息不足时拒绝提炼（防噪音）"""
    from yuanzhu.dialog.buffer import message_buffer
    message_buffer.clear()
    message_buffer.push({"text": {"content": "仅一条"}})

    resp = await client.post("/api/dialog/refine", json={"min_messages": 3})
    assert resp.status_code == 400
    assert "不足" in resp.json()["detail"]


async def test_no_message_persisted(client, db_session):
    """合规：DB 里查不到任何消息原文表"""
    from yuanzhu.db.database import Base
    tables = set(Base.metadata.tables.keys())
    assert not any("message" in t for t in tables), f"不应存在消息表: {tables}"
