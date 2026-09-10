"""meeting 模板测试：非 QA 域的四段式实测（H3 跨域预演 + 指南验证）"""
import pytest
from pathlib import Path

from yuanzhu.evals.runner import EvalsRunner
from yuanzhu.template.store import TemplateStore
from yuanzhu.ontology.object_store import ObjectStore
from yuanzhu.workflow.engine import WorkflowEngine
from yuanzhu.staged.state_machine import StagedStateMachine

MEETING_DIR = Path(__file__).resolve().parents[2] / "templates" / "meeting"


@pytest.fixture
async def meeting_registered(db_session):
    await TemplateStore(db_session).register_dir(MEETING_DIR)
    return db_session


async def test_meeting_evals_all_pass(meeting_registered):
    """meeting 模板 3 条评测全绿（L1 登记/L2 人审/语义拦截）"""
    report = await EvalsRunner(meeting_registered).run_template("meeting")
    assert report["total"] == 3
    assert report["passed"] == 3, [c for c in report["cases"] if not c["ok"]]
    names = {c["name"] for c in report["cases"]}
    assert "建会议-自动生效" in names
    assert "完成行动项-语义拦截" in names


async def test_extract_actions_workflow(meeting_registered, monkeypatch):
    """extract-actions 工作流：AI 提炼（mock）→ 逐条 staged"""
    import yuanzhu.workflow.engine as engine_mod
    async def fake_chat(model, prompt, **kw):
        return '''[{"title": "补齐接口文档", "owner": "小李", "due": "周三"},
                   {"title": "演示原型", "owner": "小王", "due": "周五"}]'''
    monkeypatch.setattr(engine_mod, "call_model", fake_chat)

    result = await WorkflowEngine(meeting_registered).run(
        domain="meeting", workflow_name="extract-actions",
        params={"raw_notes": "小李周三前补齐接口文档；小王下周五演示原型"},
        run_by="test",
    )
    submit = result["steps"]["submit"]
    assert submit["staged_count"] == 2

    pending = await StagedStateMachine(meeting_registered).list_pending()
    titles = {p.params_json["title"] for p in pending}
    assert titles == {"补齐接口文档", "演示原型"}


async def test_meeting_domain_isolated(meeting_registered):
    """meeting 域注册不影响 aiqa 域对象"""
    from yuanzhu.ontology.object_store import ObjectStore
    store = ObjectStore(meeting_registered)
    aiqa_bug = await store.get_type_by_name("aiqa", "Bug")
    assert aiqa_bug is None  # aiqa 未注册过，互不污染
    meeting = await store.get_type_by_name("meeting", "Meeting")
    assert meeting is not None
