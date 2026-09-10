"""用量审计 API 测试"""
import pytest
from httpx import AsyncClient, ASGITransport

from yuanzhu.main import app
from yuanzhu.db.database import get_db
from yuanzhu.db.models import ModelUsage


@pytest.fixture
async def client(db_session):
    async def override():
        yield db_session

    app.dependency_overrides[get_db] = override
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


async def test_usage_summary(client, db_session):
    db_session.add(ModelUsage(model="deepseek-chat", task_id=1, caller="ai-step",
                              prompt_tokens=100, completion_tokens=50, estimated_cost=0.01))
    db_session.add(ModelUsage(model="deepseek-chat", task_id=2, caller="ai-step",
                              prompt_tokens=200, completion_tokens=80, estimated_cost=0.02))
    db_session.add(ModelUsage(model="qwen-plus", task_id=None, caller="web",
                              prompt_tokens=10, completion_tokens=5, estimated_cost=0.0))
    await db_session.commit()

    resp = await client.get("/api/usage?days=7")
    assert resp.status_code == 200
    data = resp.json()
    by_model = {s["model"]: s for s in data["summary"]}
    assert by_model["deepseek-chat"]["calls"] == 2
    assert by_model["deepseek-chat"]["prompt_tokens"] == 300
    assert len(data["recent"]) == 3
