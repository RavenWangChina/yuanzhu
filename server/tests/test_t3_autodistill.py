"""T3 采纳即沉淀：approve metaflow/SaveAnswer → 自动产生洞见候选（staged）"""
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


async def test_approve_answer_triggers_distill(client, db_session):
    """采纳深度答案 → 自动出现洞见候选（staged 待轻确认）"""
    # 造一条 SaveAnswer 待审
    resp = await client.post("/mcp", json={
        "method": "tools/call",
        "params": {"name": "execute_metaflow_saveanswer",
                   "arguments": {"question": "该不该自建中台",
                                 "content": "【结论】分情况…"}},
    }, headers={"X-Agent-ID": "t"})
    assert resp.status_code == 200
    exec_id = resp.json()["exec_id"]

    # 采纳
    resp = await client.post(f"/api/staged/{exec_id}/approve", json={
        "reviewed_by": "tester", "review_comment": "采纳"})
    assert resp.status_code == 200

    # 待审中心应出现 DistillInsight 候选（auto-distill）
    resp = await client.get("/api/staged/pending")
    pending = resp.json()
    insights = [p for p in pending if "DistillInsight" in p.get("action", "")]
    assert insights, f"洞见候选未自动产生: {[p['action'] for p in pending]}"
    assert "自建中台" in str(insights[0]["params"]) or "托管" in str(insights[0]["params"])
