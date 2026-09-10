"""引擎升级测试：prompt_vars 多上游绑定（视角对抗/综合裁决的地基）"""
import pytest
from pathlib import Path

from yuanzhu.workflow.engine import WorkflowEngine
from yuanzhu.template.store import TemplateStore

AIQA_DIR = Path(__file__).resolve().parents[2] / "templates" / "aiqa"


@pytest.fixture
async def domain(db_session):
    """注册一个含 prompt_vars 的工作域（用临时模板写在 forge 目录）"""
    import yaml
    tpl = Path(__file__).resolve().parents[2] / "templates" / "forge" / "_pv_test"
    (tpl / "ontology").mkdir(parents=True, exist_ok=True)
    (tpl / "workflows").mkdir(exist_ok=True)
    (tpl / "manifest.yaml").write_text(
        "name: pv\nversion: 0.1.0\ndomain: pv\n", encoding="utf-8")
    (tpl / "ontology" / "object-types.yaml").write_text(
        "types:\n  - name: Note\n    properties: {title: {type: string}}\n",
        encoding="utf-8")
    (tpl / "workflows" / "debate.yaml").write_text(yaml.dump({
        "name": "debate",
        "params_schema": [{"name": "q", "label": "问题", "type": "text", "required": True}],
        "steps": [
            {"id": "view-a", "type": "ai_step",
             "prompt_prefix": "视角A：就问题给方案。", "prompt_var": "q",
             "model": "glm-5.1", "output": "ans_a"},
            {"id": "view-b", "type": "ai_step",
             "prompt_prefix": "视角B：针对视角A的方案提最强反驳。",
             "prompt_var": "ans_a", "model": "glm-5.1", "output": "ans_b"},
            {"id": "verdict", "type": "ai_step",
             "prompt_prefix": "综合裁决：权衡以下两方输入给最终结论。",
             "prompt_vars": ["ans_a", "ans_b"],   # ← 多上游绑定（本次升级）
             "model": "glm-5.1", "output": "final"},
        ],
    }, allow_unicode=True))
    await TemplateStore(db_session).register_dir(tpl)
    import shutil
    shutil.rmtree(tpl, ignore_errors=True)
    return db_session


async def test_prompt_vars_receives_all_upstream(domain, monkeypatch):
    """综合步收到全部上游输出（带标注块）"""
    import yuanzhu.workflow.engine as engine_mod
    calls = []

    async def fake_chat(model, prompt, **kw):
        calls.append(prompt)
        if len(calls) == 1:
            return "方案A：自建，省成本。"
        if len(calls) == 2:
            return "反驳：维护成本被低估。"
        return "最终：折中。"

    monkeypatch.setattr(engine_mod, "call_model", fake_chat)

    result = await WorkflowEngine(domain).run(
        domain="pv", workflow_name="debate", params={"q": "该不该自建中台"}, run_by="t")

    # 第 2 次调用收到视角A输出
    assert "方案A：自建" in calls[1]
    # 第 3 次调用收到 A 和 B 两方（多绑定）
    assert "方案A：自建" in calls[2]
    assert "反驳：维护成本被低估" in calls[2]
    # 输出绑定正常
    assert result["steps"]["verdict"]["result"] == "最终：折中。"
