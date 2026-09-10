"""evals 执行器测试：跑 AIQA 模板自带的评测用例（硬化清单 evals 项）"""
import pytest
from pathlib import Path

from yuanzhu.evals.runner import EvalsRunner
from yuanzhu.template.store import TemplateStore

AIQA_DIR = Path(__file__).resolve().parents[2] / "templates" / "aiqa"


@pytest.fixture
async def aiqa_registered(db_session):
    await TemplateStore(db_session).register_dir(AIQA_DIR)
    return db_session


async def test_aiqa_evals_all_pass(aiqa_registered):
    """AIQA 模板 3 条评测用例全绿（模板=平台第一批真实用户，spec 5）"""
    runner = EvalsRunner(aiqa_registered)
    report = await runner.run_template("aiqa")

    assert report["total"] == 3
    assert report["passed"] == 3
    assert report["failed"] == 0
    assert all(c["ok"] for c in report["cases"])

    # 用例名齐全
    names = {c["name"] for c in report["cases"]}
    assert "注册模块-自动生效" in names
    assert "提交缺陷-人审后入库" in names
    assert "解决缺陷-语义拦截" in names


async def test_eval_case_semantics(aiqa_registered):
    """评测语义抽查：人审后 Bug 真入库；二次 Resolve 被语义拦截"""
    from yuanzhu.ontology.object_store import ObjectStore
    from yuanzhu.staged.state_machine import StagedStateMachine

    runner = EvalsRunner(aiqa_registered)
    report = await runner.run_template("aiqa")
    assert report["passed"] == 3

    obj_store = ObjectStore(aiqa_registered)
    bug_type = await obj_store.get_type_by_name("aiqa", "Bug")
    bugs = await obj_store.list_objects(type_id=bug_type.id)
    assert any(b.properties["title"] == "eval-登录超时" for b in bugs)

    # 二次 Resolve 的动作被拒（error_contains: submission_criteria 断言已过）
    sm = StagedStateMachine(aiqa_registered)
    rejects = await sm.list_pending()
    assert len(rejects) == 0  # 全部被 approve 或根本没进 staged
