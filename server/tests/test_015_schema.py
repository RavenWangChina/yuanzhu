"""0.1.5 T1-T3：forge prompt schema 补全 + 引擎容错 + forge dry-run"""
import pytest
from pathlib import Path

from yuanzhu.main import app
from yuanzhu.db.database import get_db
from yuanzhu.template.store import TemplateStore
from yuanzhu.template.forge import dry_run_workflow

METAFLOW_DIR = Path(__import__("yuanzhu.__init__", fromlist=["__file__"]).__file__).parent / "templates" / "metaflow"


# ---------- T2 引擎容错 ----------

async def test_t2_query_step_missing_object_type_400(db_session):
    """query_step 缺 object_type → 400 带说明（不再是 500 KeyError）"""
    async def override():
        yield db_session
    app.dependency_overrides[get_db] = override
    from httpx import AsyncClient, ASGITransport
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://t") as c:
            # 构造一个缺 object_type 的 query_step（模拟 forge 产物）
            resp = await c.post("/api/workflows/run", json={
                "domain": "metaflow", "workflow": "deep-answer",
                "params": {"question": "x"}, "run_by": "t",
            })
            # 这个走的是正常路径——直接测引擎层
    finally:
        app.dependency_overrides.clear()

    from yuanzhu.workflow.engine import WorkflowEngine
    engine = WorkflowEngine(db_session)

    with pytest.raises(ValueError, match="object_type"):
        await engine._query_step({"id": "q1", "type": "query_step", "query": {"type": "Bug"}})


async def test_t2_query_step_wrong_key_hint(db_session):
    """常见 forge 错误（query.type 代替 object_type）给修复提示"""
    from yuanzhu.workflow.engine import WorkflowEngine
    engine = WorkflowEngine(db_session)

    with pytest.raises(ValueError, match="query.type|object_type"):
        await engine._query_step({"id": "q1", "type": "query_step", "query": {"type": "Bug"}})


# ---------- T3 forge dry-run ----------

async def test_t3_dry_run_valid(db_session):
    """有效工作流 → dry_run 通过"""
    await TemplateStore(db_session).register_dir(METAFLOW_DIR)
    from sqlalchemy import select
    from yuanzhu.db.models import Template
    tpl = (await db_session.execute(
        select(Template).where(Template.name == "metaflow"))).scalar_one()
    for wf in tpl.workflows_json:
        errors = dry_run_workflow(wf)
        assert not errors, f"内置模板 {wf['name']} dry-run 挂了: {errors}"


async def test_t3_dry_run_catches_schema_errors():
    """forge 典型错误 → dry_run 报告每条问题"""
    bad_wf = {
        "name": "bad",
        "steps": [
            {"id": "q1", "type": "query_step", "query": {"type": "Bug"}},   # 缺 object_type
            {"id": "a1", "type": "ai_step", "prompt_var": "$steps.q1.result"},  # $steps 语法
            {"id": "x1", "type": "unknown_step"},   # 未知类型
        ],
    }
    errors = dry_run_workflow(bad_wf)
    assert any("object_type" in e for e in errors)
    assert any("$steps" in e for e in errors)
    assert any("unknown_step" in e for e in errors)


async def test_t3_forge_rejects_bad_workflow(db_session, monkeypatch):
    """forge 产出 dry-run 不过的模板 → 拒绝（fail fast 而非留草稿让人踩坑）"""
    import yuanzhu.template.forge as forge_mod
    bad_template = {
        "manifest": {"name": "drytest", "version": "0.1.0", "domain": "drytest",
                     "description": "test"},
        "object_types": [
            {"name": "T", "title_key": "title", "exposed": True,
             "properties": {"title": {"type": "string", "required": True}}},
        ],
        "link_types": [],
        "actions": [
            {"name": "CreateT", "description_for_agent": "create",
             "autonomy_level": 2, "requires_staging": True,
             "params": {"type": "object", "properties": {"title": {"type": "string"}},
                        "required": ["title"]},
             "transform": [{"create_object": {"type": "T"},
                            "with": {"title": "from:params.title"}}]},
        ],
        "workflows": [
            {"name": "bad-wf", "description": "bad",
             "params_schema": [{"name": "title", "label": "T", "type": "string", "required": True}],
             "steps": [
                 {"id": "q1", "type": "query_step", "query": {"type": "T"}},  # 缺 object_type
                 {"id": "s1", "type": "action_step", "action": "CreateT",
                  "params": {"title": "$params.title"}},
             ]},
        ],
        "evals": [
            {"name": "test",
             "steps": [{"action": "CreateT", "params": {"title": "eval-t"},
                        "expect": {"status": "staged"}},
                       {"approve": {}}],
             "expect": {"status": "applied",
                        "object_exists": {"type": "T", "title": "eval-t"}}},
        ],
    }

    async def fake_gen(d):
        return dict(bad_template)
    monkeypatch.setattr(forge_mod, "generate_template_json", fake_gen)

    with pytest.raises(ValueError, match="dry-run|object_type"):
        await forge_mod.forge_template(db_session, "测试")
