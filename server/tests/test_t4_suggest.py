"""T4 重复模式检测：问答历史 → AI 判断例行公事 → 建议铸工作流"""
import pytest
from pathlib import Path

from yuanzhu.main import app
from yuanzhu.db.database import get_db
from yuanzhu.template.store import TemplateStore

METAFLOW_DIR = Path(__import__("yuanzhu.__init__", fromlist=["__file__"]).__file__).parent / "templates" / "metaflow"


@pytest.fixture
async def client(db_session, monkeypatch):
    async def override():
        yield db_session
    app.dependency_overrides[get_db] = override

    import yuanzhu.workflow.engine as engine_mod
    async def fake_chat(model, prompt, session=None, **kw):
        # suggest-workflow 的判断调用
        return '{"suggested": true, "reason": "你最近 3 个问题都在问周报汇总相关——这看起来是每周例行公事", "description": "我每周五需要收集各小组的工作进展，汇总成一份部门周报"}'
    monkeypatch.setattr(engine_mod, "call_model", fake_chat)

    await TemplateStore(db_session).register_dir(METAFLOW_DIR)

    from httpx import AsyncClient, ASGITransport
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as c:
        yield c
    app.dependency_overrides.clear()


async def _add_answer(db_session, question, content):
    """直接造已采纳的 Answer 对象（模拟历史问答）"""
    from yuanzhu.models.object import ObjectCreate
    from yuanzhu.ontology.object_store import ObjectStore
    store = ObjectStore(db_session)
    t = await store.get_type_by_name("metaflow", "Answer")
    await store.create_object(ObjectCreate(
        type_id=t.id,
        properties={"question": question, "content": content, "adopted_by": "chat"},
    ))


async def test_suggest_needs_enough_history(client, db_session):
    """历史不足：不建议（防噪音）"""
    resp = await client.post("/api/metaflow/suggest-workflow", json={})
    assert resp.status_code == 200
    assert resp.json()["suggested"] is False
    assert "不足" in resp.json()["reason"] or "历史" in resp.json()["reason"]


async def test_suggest_detects_pattern(client, db_session):
    """3 条相关历史 → AI 判定模式 → 建议含理由与 forge 描述"""
    await _add_answer(db_session, "帮我把本周各组进展汇总成周报", "【结论】……")
    await _add_answer(db_session, "上周的周报汇总还没发，帮我整理", "【结论】……")
    await _add_answer(db_session, "这周各组进展如何，该出周报了", "【结论】……")
    await db_session.commit()

    resp = await client.post("/api/metaflow/suggest-workflow", json={})
    assert resp.status_code == 200
    d = resp.json()
    assert d["suggested"] is True
    assert "周报" in d["reason"]
    assert "周报" in d["description"]     # forge 描述可直接喂 forge
