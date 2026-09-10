"""工作流触发端点测试（H2 路径：模板市场「使用」→ 任务 → 待审）"""
import pytest
from httpx import AsyncClient, ASGITransport
from pathlib import Path

from yuanzhu.main import app
from yuanzhu.db.database import get_db
from yuanzhu.template.store import TemplateStore

AIQA_DIR = Path(__file__).resolve().parents[2] / "templates" / "aiqa"


@pytest.fixture
async def client(db_session, monkeypatch):
    async def override():
        yield db_session

    app.dependency_overrides[get_db] = override

    # ai_step 模型 mock
    import yuanzhu.workflow.engine as engine_mod
    async def fake_chat(model: str, prompt: str) -> str:
        return "风险中等，建议回归支付模块。"
    monkeypatch.setattr(engine_mod, "call_model", fake_chat)

    await TemplateStore(db_session).register_dir(AIQA_DIR)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


async def test_run_workflow_endpoint(client):
    """POST /api/workflows/run：触发报告工作流 → Report 进待审"""
    # 种一个 Open Bug 供 query_step 查到
    resp = await client.post("/api/objects/types", json={
        "name": "Bug", "domain": "aiqa", "title_key": "title",
        "properties": {"title": {"type": "string", "required": True},
                       "status": {"type": "string", "enum": ["Open", "Closed"], "default": "Open"}},
    })
    type_id = resp.json()["id"]
    await client.post("/api/objects", json={
        "type_id": type_id,
        "properties": {"title": "支付超时", "status": "Open"},
    })

    resp = await client.post("/api/workflows/run", json={
        "domain": "aiqa",
        "workflow": "test-report",
        "params": {"report_title": "H2 真人测试报告"},
        "run_by": "web-user",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["workflow"] == "test-report"
    assert data["steps"]["publish"]["status"] == "staged"

    # 待审中心可见（H2 测试者的第二步任务）
    resp = await client.get("/api/staged/pending")
    assert any(p["params"].get("title") == "H2 真人测试报告" for p in resp.json())


async def test_run_unknown_workflow_400(client):
    resp = await client.post("/api/workflows/run", json={
        "domain": "aiqa", "workflow": "no-such", "params": {}, "run_by": "x",
    })
    assert resp.status_code == 400


async def test_workflow_params_schema_exposed(client):
    """模板详情暴露工作流参数声明（前端弹窗渲染依据）"""
    resp = await client.get("/api/templates?domain=aiqa")
    tpl = resp.json()[0]
    wf = next(w for w in tpl["workflows_json"] if w["name"] == "test-report")
    assert "params_schema" in wf
    assert any(p["name"] == "report_title" for p in wf["params_schema"])
