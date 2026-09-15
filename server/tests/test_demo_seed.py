"""v0.2.0 First 5 Minutes：demo 域模板 + yuanzhu-demo 种子数据"""
import pytest
from pathlib import Path

import yuanzhu
from yuanzhu.template.store import TemplateStore

DEMO_DIR = Path(yuanzhu.__file__).parent / "templates" / "demo"


async def test_demo_template_registers(db_session):
    """demo 域四段式可注册（manifest/ontology/actions/workflows/evals 齐全）"""
    tpl = await TemplateStore(db_session).register_dir(DEMO_DIR)
    assert tpl.domain == "demo"
    assert tpl.status == "published"  # evals 全过自动上架
    wf_names = [w["name"] for w in tpl.workflows_json]
    assert "add-task" in wf_names


async def test_demo_seed_creates_staged_and_applied(db_session, monkeypatch):
    """种子逻辑：AI 提交待审（staged）+ 一条批准入库 + 洞见"""
    # demo.py._seed 用 async_session_factory——指到测试库
    from sqlalchemy.ext.asyncio import async_sessionmaker
    import yuanzhu.db.database as db_mod
    monkeypatch.setattr(db_mod, "async_session_factory",
                        async_sessionmaker(db_session.bind, expire_on_commit=False))
    # 模板注册依赖 lifespan 之外的手动注册（demo 场景同 _seed）
    await TemplateStore(db_session).register_dir(DEMO_DIR)
    await db_session.commit()

    from yuanzhu.demo import _seed
    stats = await _seed(8600)
    assert stats["staged"] >= 3, "AI 待审条目至少 3 条"
    assert stats["objects"] >= 1, "至少 1 条已批准入库"

    # staged 状态断言
    from sqlalchemy import select
    from yuanzhu.db.models import ActionExec
    execs = (await db_session.execute(
        select(ActionExec).where(ActionExec.status == "staged"))).scalars().all()
    assert any(e.staged_by == "demo-assistant" for e in execs)
