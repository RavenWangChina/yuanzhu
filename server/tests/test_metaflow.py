"""metaflow 模板测试：注册/evals/工作流编排（mock AI）"""
import pytest
from pathlib import Path

from yuanzhu.evals.runner import EvalsRunner
from yuanzhu.template.store import TemplateStore
from yuanzhu.workflow.engine import WorkflowEngine
from yuanzhu.staged.state_machine import StagedStateMachine

METAFLOW_DIR = Path(__file__).resolve().parents[2] / "templates" / "metaflow"


@pytest.fixture
async def metaflow(db_session):
    await TemplateStore(db_session).register_dir(METAFLOW_DIR)
    return db_session


async def test_metaflow_evals(metaflow):
    report = await EvalsRunner(metaflow).run_template("metaflow")
    assert report["passed"] == report["total"] == 2


async def test_deep_answer_pipeline(metaflow, monkeypatch):
    """deep-answer 六步编排：recall→澄清→A→B→审查→综合→保存（staged）"""
    import yuanzhu.workflow.engine as engine_mod
    prompts = []

    async def fake_chat(model, prompt, **kw):
        prompts.append(prompt)
        if len(prompts) == 1:
            return "两种理解：a/b；缺团队规模信息"
        if len(prompts) == 2:
            return "视角A：自建，三个步骤"
        if len(prompts) == 3:
            return "视角B反驳：维护成本被低估"
        if len(prompts) == 4:
            return "审查：矛盾在成本估算；共同盲区是退出成本"
        return "【结论】分情况；【置信度】中"

    monkeypatch.setattr(engine_mod, "call_model", fake_chat)

    result = await WorkflowEngine(metaflow).run(
        domain="metaflow", workflow_name="deep-answer",
        params={"question": "该不该自建中台"}, run_by="t")

    # 六步全部执行，最终 staged 等人采纳
    assert result["steps"]["save"]["status"] == "staged"
    # 审查步收到 A+B（多上游）
    assert "视角A" in prompts[3] and "视角B" in prompts[3]
    # 综合步收到三方
    assert all(k in prompts[4] for k in ("视角A", "视角B", "审查"))
    # 待审中心有答案
    pending = await StagedStateMachine(metaflow).list_pending()
    assert any("该不该自建中台" in str(p.params_json) for p in pending)


async def test_insight_recall_feeds_clarify(metaflow, monkeypatch):
    """知识环：已有 Insight 时，澄清步收到历史洞见"""
    from yuanzhu.models.object import ObjectCreate
    from yuanzhu.ontology.object_store import ObjectStore
    store = ObjectStore(metaflow)
    insight_type = await store.get_type_by_name("metaflow", "Insight")
    await store.create_object(ObjectCreate(
        type_id=insight_type.id,
        properties={"takeaway": "20人以下团队优先托管方案", "context": "团队规模小于20"}))

    import yuanzhu.workflow.engine as engine_mod
    seen = []

    async def fake_chat(model, prompt, **kw):
        seen.append(prompt)
        return "ok"

    monkeypatch.setattr(engine_mod, "call_model", fake_chat)
    await WorkflowEngine(metaflow).run(
        domain="metaflow", workflow_name="deep-answer",
        params={"question": "any"}, run_by="t")

    assert "20人以下团队优先托管方案" in seen[0], "历史洞见未反哺澄清步"
