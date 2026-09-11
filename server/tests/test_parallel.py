"""T5 引擎并行步骤组：{"parallel": [step, ...]}——组内并发，全完成后续"""
import asyncio
import time
import pytest
from pathlib import Path

import yaml

from yuanzhu.workflow.engine import WorkflowEngine
from yuanzhu.template.store import TemplateStore


@pytest.fixture
async def ptest(db_session):
    tpl = Path(__import__("yuanzhu.__init__", fromlist=["__file__"]).__file__).parent / "templates" / "forge" / "_par_test"
    (tpl / "ontology").mkdir(parents=True, exist_ok=True)
    (tpl / "workflows").mkdir(exist_ok=True)
    (tpl / "manifest.yaml").write_text("name: par\nversion: 0.1.0\ndomain: par\n", encoding="utf-8")
    (tpl / "ontology" / "object-types.yaml").write_text(
        "types:\n  - name: Note\n    properties: {title: {type: string}}\n", encoding="utf-8")
    (tpl / "workflows" / "race.yaml").write_text(yaml.dump({
        "name": "race",
        "params_schema": [{"name": "q", "label": "Q", "type": "text", "required": True}],
        "steps": [
            {"parallel": [
                {"id": "a", "type": "ai_step", "prompt_prefix": "A", "prompt_var": "q",
                 "model": "glm-5.1", "output": "out_a"},
                {"id": "b", "type": "ai_step", "prompt_prefix": "B", "prompt_var": "q",
                 "model": "glm-5.1", "output": "out_b"},
            ]},
            {"id": "join", "type": "ai_step", "prompt_prefix": "汇总",
             "prompt_vars": ["out_a", "out_b"], "model": "glm-5.1", "output": "final"},
        ],
    }, allow_unicode=True))
    await TemplateStore(db_session).register_dir(tpl)
    import shutil
    shutil.rmtree(tpl, ignore_errors=True)
    return db_session


async def test_parallel_group_runs_concurrently(ptest, monkeypatch):
    """组内两步真并发（各 sleep 0.4s，总耗时应 ≈0.4s 而非 0.8s）"""
    import yuanzhu.workflow.engine as engine_mod

    async def fake_chat(model, prompt, **kw):
        await asyncio.sleep(0.4)
        return f"done:{prompt}"   # 返回完整 prompt，供 join 验证块接收

    monkeypatch.setattr(engine_mod, "call_model", fake_chat)

    t0 = time.monotonic()
    result = await WorkflowEngine(ptest).run(
        domain="par", workflow_name="race", params={"q": "x"}, run_by="t")
    elapsed = time.monotonic() - t0

    # join 步收到两个并行输出（result=完整 prompt 回显，含两个标注块）
    join_result = result["steps"]["join"]["result"]
    assert "【out_a】" in join_result
    assert "【out_b】" in join_result
    # 并发性：0.4+0.4+0.4 顺序=1.2s；并行≈0.8s。阈值 1.05 容忍调度
    assert elapsed < 1.05, f"并行未生效: {elapsed:.2f}s"


async def test_parallel_failure_names_the_step(ptest, monkeypatch):
    """并行组一步挂：报错指明是哪步"""
    import yuanzhu.workflow.engine as engine_mod

    async def fake_chat(model, prompt, **kw):
        if prompt.startswith("B"):
            raise ValueError("模型B炸了")
        return "a-ok"

    monkeypatch.setattr(engine_mod, "call_model", fake_chat)
    with pytest.raises(ValueError, match="b"):
        await WorkflowEngine(ptest).run(
            domain="par", workflow_name="race", params={"q": "x"}, run_by="t")
