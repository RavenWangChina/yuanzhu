"""v0.1.6 自举开关：toggle 端点 + BehaviorLog + 行为记录点"""
import pytest
from pathlib import Path

from yuanzhu.main import app
from yuanzhu.db.database import get_db
from yuanzhu.db.models import BehaviorLog
from yuanzhu.template.store import TemplateStore

METAFLOW_DIR = Path(__import__("yuanzhu.__init__", fromlist=["__file__"]).__file__).parent / "templates" / "metaflow"


@pytest.fixture
async def client(db_session, db_engine, monkeypatch):
    async def override():
        yield db_session
    app.dependency_overrides[get_db] = override
    await TemplateStore(db_session).register_dir(METAFLOW_DIR)

    # run-async 的 session factory 指到测试库
    from sqlalchemy.ext.asyncio import async_sessionmaker
    import yuanzhu.db.database as db_mod
    monkeypatch.setattr(db_mod, "async_session_factory", async_sessionmaker(db_engine, expire_on_commit=False))

    import yuanzhu.workflow.engine as engine_mod
    async def fake_chat(model, prompt, session=None, **kw):
        return "模拟回复"
    monkeypatch.setattr(engine_mod, "call_model", fake_chat)

    from httpx import AsyncClient, ASGITransport
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as c:
        yield c
    app.dependency_overrides.clear()


async def test_bootstrap_default_off(client):
    """默认关闭"""
    resp = await client.get("/api/bootstrap/status")
    assert resp.status_code == 200
    assert resp.json()["enabled"] is False


async def test_bootstrap_toggle(client):
    """切换开→关"""
    # 开
    resp = await client.post("/api/bootstrap/toggle")
    assert resp.json()["enabled"] is True

    # 关
    resp = await client.post("/api/bootstrap/toggle")
    assert resp.json()["enabled"] is False


async def test_behavior_logged_when_enabled(client, db_session):
    """开启时行为被记录"""
    # 开启
    await client.post("/api/bootstrap/toggle")

    # 跑一个工作流
    resp = await client.post("/api/workflows/run", json={
        "domain": "metaflow", "workflow": "deep-answer",
        "params": {"question": "测试行为记录"}, "run_by": "test",
    })
    assert resp.status_code == 200

    # 行为日志应有 ask 记录
    from sqlalchemy import select
    logs = (await db_session.execute(
        select(BehaviorLog).where(BehaviorLog.action == "ask"))).scalars().all()
    assert len(logs) >= 1
    assert "测试行为记录" in str(logs[0].detail_json or "")


async def test_no_behavior_when_disabled(client, db_session):
    """关闭时行为不被记录"""
    # 确保关闭（默认就是关）
    resp = await client.get("/api/bootstrap/status")
    if resp.json()["enabled"]:
        await client.post("/api/bootstrap/toggle")

    resp = await client.post("/api/workflows/run", json={
        "domain": "metaflow", "workflow": "deep-answer",
        "params": {"question": "不应记录"}, "run_by": "test",
    })
    assert resp.status_code == 200

    from sqlalchemy import select
    logs = (await db_session.execute(
        select(BehaviorLog).where(BehaviorLog.action == "ask"))).scalars().all()
    assert len(logs) == 0


async def test_behavior_recent_api(client, db_session):
    """GET /api/behavior/recent"""
    resp = await client.get("/api/behavior/recent?limit=10")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
