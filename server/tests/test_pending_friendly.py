"""待审 API 友好化测试：action_description（H2 卡点修复的看守）"""
import pytest
from httpx import AsyncClient, ASGITransport
from pathlib import Path

from yuanzhu.main import app
from yuanzhu.db.database import get_db
from yuanzhu.template.store import TemplateStore

AIQA_DIR = Path(__file__).resolve().parents[2] / "templates" / "aiqa"


async def test_pending_includes_friendly_description(db_session):
    """待审条目带 action_description（小白看得懂的中文动作说明）"""
    async def override():
        yield db_session
    app.dependency_overrides[get_db] = override
    await TemplateStore(db_session).register_dir(AIQA_DIR)

    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://t") as c:
            # 造一条待审（CreateBug staged）
            resp = await c.post("/mcp", json={
                "method": "tools/call",
                "params": {"name": "execute_aiqa_createbug",
                           "arguments": {"title": "友好描述测试", "severity": "minor"}},
            }, headers={"X-Agent-ID": "t"})
            assert resp.status_code == 200

            resp = await c.get("/api/staged/pending")
            items = resp.json()
            assert len(items) == 1
            item = items[0]
            # 动作仍是技术名（审计需要），但加了友好描述
            assert item["action"] == "aiqa/CreateBug"
            assert item["action_description"] == "提交一个新缺陷（进入待审中心等人确认）"
    finally:
        app.dependency_overrides.clear()
