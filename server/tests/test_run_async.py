"""T1 异步工作流：run-async 立返 task_id + status 轮询（真实步骤进度）"""
import asyncio
import time
import pytest
from pathlib import Path

from yuanzhu.main import app
from yuanzhu.db.database import get_db
from yuanzhu.template.store import TemplateStore

METAFLOW_DIR = Path(__import__("yuanzhu.__init__", fromlist=["__file__"]).__file__).parent / "templates" / "metaflow"


@pytest.fixture
async def client(db_session, db_engine, monkeypatch):
    async def override():
        yield db_session
    app.dependency_overrides[get_db] = override
    await TemplateStore(db_session).register_dir(METAFLOW_DIR)

    # run-async 的后台 runner 用全局 session factory——指到测试内存库
    from sqlalchemy.ext.asyncio import async_sessionmaker
    import yuanzhu.db.database as db_mod
    monkeypatch.setattr(db_mod, "async_session_factory", async_sessionmaker(db_engine, expire_on_commit=False))

    import yuanzhu.workflow.engine as engine_mod
    async def fake_chat(model, prompt, session=None, **kw):
        await asyncio.sleep(0.3)
        return "[]" if "提取" in prompt or "行动项" in prompt else "模拟回复"
    monkeypatch.setattr(engine_mod, "call_model", fake_chat)

    from httpx import AsyncClient, ASGITransport
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as c:
        yield c
    app.dependency_overrides.clear()
    # 清全局任务表
    from yuanzhu.workflow import tasks as wt
    wt._TASKS.clear()


async def test_run_async_lifecycle(client):
    """提交即返 task_id；轮询见真实步骤推进；完成取结果"""
    import json as _json
    resp = await client.post("/api/workflows/run-async", json={
        "domain": "metaflow", "workflow": "deep-answer",
        "params": {"question": "测试问题"}, "run_by": "t",
    })
    assert resp.status_code == 200
    task_id = resp.json()["task_id"]
    assert task_id

    # 轮询直到完成（fake 每步 0.3s，六步约 2s）
    deadline = time.monotonic() + 15
    saw_progress = False
    final = None
    while time.monotonic() < deadline:
        r = (await client.get(f"/api/workflows/status/{task_id}")).json()
        if r["done_steps"] and not r["done"]:
            saw_progress = True     # 中间态：部分步骤完成
        if r["done"]:
            final = r
            break
        await asyncio.sleep(0.2)

    assert final is not None, "任务未在期限内完成"
    assert saw_progress, "未观察到中间进度（真实步骤推进不可见）"
    assert final["status"] == "done"
    # 结果里 verdict 存在
    assert "verdict" in (final.get("result") or {}).get("steps", {})


async def test_status_unknown_task(client):
    resp = await client.get("/api/workflows/status/no-such-id")
    assert resp.status_code == 404
