"""CLI（yuanzhu 命令）测试——ADR-012：开发者第一界面，API 薄壳

httpx.AsyncClient + ASGITransport 直连 app（不起真端口）。
"""
import pytest
from pathlib import Path

from yuanzhu.main import app
from yuanzhu.db.database import get_db
from yuanzhu.template.store import TemplateStore

AIQA_DIR = Path(__import__("yuanzhu.__init__", fromlist=["__file__"]).__file__).parent / "templates" / "aiqa"


@pytest.fixture
async def setup(db_session):
    async def override():
        yield db_session
    app.dependency_overrides[get_db] = override
    yield db_session
    app.dependency_overrides.clear()


async def run_cli(setup, *argv):
    """绑定测试库跑 CLI（直接 await _amain，绕开 asyncio.run 的 loop 限制）"""
    import contextlib
    import httpx
    import yuanzhu.cli as cli_mod
    from yuanzhu.cli import build_parser, Ctx, _amain

    transport = httpx.ASGITransport(app=app)
    client = httpx.AsyncClient(transport=transport, base_url="http://cli-test")

    @contextlib.asynccontextmanager
    async def fake_client():
        yield client

    original = cli_mod.make_client
    cli_mod.make_client = fake_client
    ctx = Ctx()
    try:
        args = build_parser().parse_args(list(argv))
        code = await _amain(args, ctx)
        ctx.exit_code = code if code is not None else 0
    finally:
        cli_mod.make_client = original
        await client.aclose()
    return "\n".join(ctx._lines), ctx.exit_code


async def test_status(setup):
    out, code = await run_cli(setup, "status")
    assert code == 0
    assert "ok" in out and "standalone" in out


async def test_query_objects(setup, sample_object_type):
    from yuanzhu.models.object import ObjectCreate
    from yuanzhu.ontology.object_store import ObjectStore
    store = ObjectStore(setup)
    await store.create_object(ObjectCreate(
        type_id=sample_object_type.id,
        properties={"title": "CLI 查的 Bug", "status": "Open"},
    ))

    out, code = await run_cli(setup, "query", "test", "bug", "--filter", "status=Open")
    assert code == 0
    assert "CLI 查的 Bug" in out


async def test_pending_and_approve(setup, sample_object_type, sample_action_type):
    from yuanzhu.models.object import ObjectCreate
    from yuanzhu.ontology.object_store import ObjectStore
    from yuanzhu.staged.state_machine import StagedStateMachine
    store = ObjectStore(setup)
    bug = await store.create_object(ObjectCreate(
        type_id=sample_object_type.id,
        properties={"title": "CLI Bug", "status": "Open", "priority": 1},
    ))
    sm = StagedStateMachine(setup)
    exec = await sm.stage(sample_action_type.id,
                          {"object_id": bug.id, "priority": 5}, "cli-test")

    out, code = await run_cli(setup, "pending")
    assert code == 0
    assert "ChangePriority" in out and str(exec.id) in out

    out, code = await run_cli(setup, "approve", str(exec.id), "--comment", "CLI 批准")
    assert code == 0
    assert "applied" in out

    fresh = await store.get_object(bug.id)
    assert fresh.properties["priority"] == 5


async def test_reject_requires_comment(setup, sample_object_type, sample_action_type):
    from yuanzhu.models.object import ObjectCreate
    from yuanzhu.ontology.object_store import ObjectStore
    from yuanzhu.staged.state_machine import StagedStateMachine
    store = ObjectStore(setup)
    bug = await store.create_object(ObjectCreate(
        type_id=sample_object_type.id,
        properties={"title": "拒", "status": "Open"},
    ))
    exec = await StagedStateMachine(setup).stage(
        sample_action_type.id, {"object_id": bug.id, "priority": 2}, "cli")

    out, code = await run_cli(setup, "reject", str(exec.id))
    assert code != 0
    assert "comment" in out or "理由" in out


async def test_templates_and_run(setup, monkeypatch):
    await TemplateStore(setup).register_dir(AIQA_DIR)

    out, code = await run_cli(setup, "templates")
    assert code == 0
    assert "aiqa" in out and "archaeology" in out

    import yuanzhu.workflow.engine as engine_mod
    async def fake_chat(model, prompt, **kw):
        return "[]"
    monkeypatch.setattr(engine_mod, "call_model", fake_chat)

    out, code = await run_cli(setup, "run", "aiqa", "archaeology",
                              "--param", "module_brief=登录模块")
    assert code == 0
    assert "archaeology" in out


async def test_mcp_tools(setup):
    out, code = await run_cli(setup, "mcp", "tools")
    assert code == 0
    assert "list_pending_approvals" in out
