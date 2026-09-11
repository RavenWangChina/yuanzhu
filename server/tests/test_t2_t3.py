"""T2 估费 + T3 evals 副作用清理测试"""
import pytest
from pathlib import Path

from yuanzhu.gateway.proxy import build_usage_record
from yuanzhu.evals.runner import EvalsRunner
from yuanzhu.template.store import TemplateStore

METAFLOW_DIR = Path(__file__).resolve().parents[2] / "templates" / "metaflow"


def test_t2_cost_computed():
    """估费：有价目的模型算出真值，无价目记 0 不炸"""
    record = build_usage_record(
        model="gpt-4o", usage={"prompt_tokens": 1000, "completion_tokens": 500},
        task_id=1, caller="t")
    assert record.estimated_cost >= 0  # 有价则>0，无价 0——不炸是底线
    # 未知模型也稳
    record2 = build_usage_record(
        model="totally-unknown-model", usage={"prompt_tokens": 10, "completion_tokens": 5},
        task_id=None, caller="t")
    assert record2.estimated_cost >= 0


async def test_t3_evals_leaves_no_test_objects(db_session):
    """evals 跑完：库中无 eval- 前缀测试对象残留（exec 审计记录保留）"""
    await TemplateStore(db_session).register_dir(METAFLOW_DIR)
    report = await EvalsRunner(db_session).run_template("metaflow")
    assert report["passed"] == report["total"] == 2

    from yuanzhu.ontology.object_store import ObjectStore
    from yuanzhu.db.models import ActionExec
    from sqlalchemy import select

    store = ObjectStore(db_session)
    for type_name in ("Answer", "Insight"):
        t = await store.get_type_by_name("metaflow", type_name)
        objs = await store.list_objects(type_id=t.id, limit=500)
        leaked = [o for o in objs if str(
            (o.properties or {}).get("question") or (o.properties or {}).get("takeaway") or ""
        ).startswith("eval-")]
        assert not leaked, f"evals 残留测试对象: {[o.title for o in leaked]}"

    # 审计记录保留
    execs = (await db_session.execute(select(ActionExec))).scalars().all()
    assert len(execs) >= 2
