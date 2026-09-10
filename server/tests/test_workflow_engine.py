"""工作流执行引擎测试（spec 3.2 steps：action_step / ai_step / query_step）

模型调用全部 mock——测编排逻辑（绑定/迭代/staged 语义），不打真实供应商。
"""
import pytest
from pathlib import Path

from yuanzhu.workflow.engine import WorkflowEngine
from yuanzhu.template.store import TemplateStore
from yuanzhu.ontology.object_store import ObjectStore

AIQA_DIR = Path(__file__).resolve().parents[2] / "templates" / "aiqa"


@pytest.fixture
async def aiqa_registered(db_session):
    await TemplateStore(db_session).register_dir(AIQA_DIR)
    return db_session


def _mock_ai(monkeypatch, responses: list):
    """按调用次序返回预置回复（记录调用以断言提示词分区）"""
    calls = []

    async def fake_chat(model: str, prompt: str) -> str:
        calls.append({"model": model, "prompt": prompt})
        return responses.pop(0)

    import yuanzhu.workflow.engine as engine_mod
    monkeypatch.setattr(engine_mod, "call_model", fake_chat)
    return calls


async def test_query_and_action_steps(aiqa_registered, monkeypatch):
    """query_step 查 Bug → ai_step 总结（mock）→ action_step 建 Report（staged）"""
    db = aiqa_registered
    obj_store = ObjectStore(db)

    bug_type = await obj_store.get_type_by_name("aiqa", "Bug")
    from yuanzhu.models.object import ObjectCreate
    for title in ("支付失败未回滚", "退款金额为负"):
        await obj_store.create_object(ObjectCreate(
            type_id=bug_type.id,
            properties={"title": title, "status": "Open", "severity": "major"},
        ))

    calls = _mock_ai(monkeypatch, ["总体风险：高。Top：支付失败未回滚。建议：优先修复。"])

    engine = WorkflowEngine(db)
    result = await engine.run(
        domain="aiqa",
        workflow_name="test-report",
        params={"report_title": "支付模块周报"},
        run_by="workflow-test",
    )

    assert len(calls) == 1
    assert "支付失败未回滚" in calls[0]["prompt"]  # 可变段=查询结果
    assert "测试状态报告" in calls[0]["prompt"]     # 稳定前缀在提示词里

    assert result["steps"]["publish"]["status"] == "staged"

    from yuanzhu.staged.state_machine import StagedStateMachine
    pending = await StagedStateMachine(db).list_pending()
    assert any(p.params_json.get("title") == "支付模块周报" for p in pending)


async def test_ai_step_expect_json_and_iterate(aiqa_registered, monkeypatch):
    """expect_json 解析 + iterate_over 逐项 staged"""
    db = aiqa_registered
    analysis = "要点1：下单流程\n要点2：库存扣减"
    cases = (
        '[{"name": "TC-正向-下单", "kind": "positive", "module_name": "订单",'
        ' "steps": "正常下单", "expected": "成功"},'
        '{"name": "TC-反向-超卖", "kind": "negative", "module_name": "订单",'
        ' "steps": "并发超卖", "expected": "拦截"}]'
    )
    _mock_ai(monkeypatch, [analysis, cases])

    engine = WorkflowEngine(db)
    result = await engine.run(
        domain="aiqa",
        workflow_name="archaeology",
        params={"module_brief": "订单模块：下单、库存、退款"},
        run_by="workflow-test",
    )

    submit = result["steps"]["submit-cases"]
    assert submit["staged_count"] == 2

    from yuanzhu.staged.state_machine import StagedStateMachine
    pending = await StagedStateMachine(db).list_pending()
    tc_names = [p.params_json["name"] for p in pending
                if str(p.params_json.get("name", "")).startswith("TC-")]
    assert set(tc_names) == {"TC-正向-下单", "TC-反向-超卖"}


async def test_action_step_l1_auto_applied(aiqa_registered):
    """L1 动作在工作流里自动生效，不进待审"""
    engine = WorkflowEngine(aiqa_registered)
    result = await engine.run_action(
        domain="aiqa", action_name="RegisterModule",
        params={"name": "工作流注册的模块", "owner": "engine"},
        run_by="wf",
    )
    assert result["status"] == "applied"

    obj_store = ObjectStore(aiqa_registered)
    m = await obj_store.get_type_by_name("aiqa", "Module")
    mods = await obj_store.list_objects(type_id=m.id)
    assert any(o.properties["name"] == "工作流注册的模块" for o in mods)


async def test_unknown_workflow_rejected(aiqa_registered):
    engine = WorkflowEngine(aiqa_registered)
    with pytest.raises(ValueError, match="不存在"):
        await engine.run(domain="aiqa", workflow_name="no-such",
                         params={}, run_by="x")
