"""C1 专项：evals 同库连跑两次全过（幂等键 run 隔离——审查预言第二次必挂）"""
import pytest
from pathlib import Path

from yuanzhu.evals.runner import EvalsRunner
from yuanzhu.template.store import TemplateStore

METAFLOW_DIR = Path(__import__("yuanzhu.__init__", fromlist=["__file__"]).__file__).parent / "templates" / "metaflow"


async def test_evals_twice_in_same_db(db_session):
    await TemplateStore(db_session).register_dir(METAFLOW_DIR)

    r1 = await EvalsRunner(db_session).run_template("metaflow")
    assert r1["passed"] == r1["total"] == 2

    r2 = await EvalsRunner(db_session).run_template("metaflow")   # ← 审查预言这里挂
    assert r2["passed"] == r2["total"] == 2, [c for c in r2["cases"] if not c["ok"]]
