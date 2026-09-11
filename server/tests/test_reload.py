"""T6 草稿转正：evals 报告存储 + reload 重跑评测守门"""
import pytest
from pathlib import Path

from yuanzhu.template.store import TemplateStore
from yuanzhu.template.forge import forge_template, reload_template

FORGE_ROOT = Path(__file__).resolve().parents[2] / "templates" / "forge"


@pytest.fixture(autouse=True)
def cleanup():
    import shutil
    yield
    shutil.rmtree(FORGE_ROOT, ignore_errors=True)


GOOD = {
    "manifest": {"name": "reload-test", "version": "0.1.0", "domain": "reloadtest",
                 "description": "reload 测试"},
    "object_types": [
        {"name": "Task", "title_key": "title", "exposed": True,
         "properties": {"title": {"type": "string", "required": True}}},
    ],
    "link_types": [],
    "actions": [
        {"name": "CreateTask", "description_for_agent": "建任务（人审）",
         "autonomy_level": 2, "requires_staging": True,
         "params": {"type": "object", "properties": {"title": {"type": "string"}},
                    "required": ["title"]},
         "transform": [{"create_object": {"type": "Task"},
                        "with": {"title": "from:params.title"}}]},
    ],
    "workflows": [
        {"name": "add-task", "description": "加任务",
         "params_schema": [{"name": "title", "label": "标题", "type": "string", "required": True}],
         "steps": [{"id": "submit", "type": "action_step", "action": "CreateTask",
                    "params": {"title": "$params.title"}}]},
    ],
    "evals": [
        {"name": "建任务-人审入库",
         "steps": [{"action": "CreateTask", "params": {"title": "eval-r1"},
                    "expect": {"status": "staged"}},
                   {"approve": {}}],
         "expect": {"status": "applied",
                    "object_exists": {"type": "Task", "title": "eval-r1"}}},
    ],
}


async def test_reload_promotes_draft(db_session, monkeypatch):
    """draft → 人修目录 → reload 重跑 → 全过升级 published"""
    import yuanzhu.template.forge as forge_mod

    # 第一次 forge：动作自主性配错（L1 自动）→ evals 挂 → draft
    bad = dict(GOOD)
    bad["actions"] = [dict(GOOD["actions"][0], autonomy_level=1, requires_staging=False)]

    gen_results = [dict(bad)]

    async def fake_gen(d):
        return gen_results.pop(0) if gen_results else dict(GOOD)
    monkeypatch.setattr(forge_mod, "generate_template_json", fake_gen)

    r1 = await forge_template(db_session, "管理任务")
    assert r1["status"] == "draft"
    assert r1["evals"]["failed"] >= 1

    # 报告已存模板（Web 可显示失败原因）
    tpl = await TemplateStore(db_session).get_by_name_version("reload-test", "0.1.0")
    report = (tpl.manifest_json or {}).get("last_evals_report") or {}
    assert report.get("failed", 0) >= 1
    assert report.get("failures")

    # 人修目录：把动作改回 L2（直接改文件——模拟人工修正）
    action_file = FORGE_ROOT / "reload-test" / "actions" / "createtask.yaml"
    action_file.write_text(action_file.read_text(encoding="utf-8").replace(
        "autonomy_level: 1", "autonomy_level: 2").replace(
        "requires_staging: false", "requires_staging: true"), encoding="utf-8")

    # reload：重读目录 + 重跑 evals → 升级
    r2 = await reload_template(db_session, "reload-test")
    assert r2["status"] == "published", r2
    tpl = await TemplateStore(db_session).get_by_name_version("reload-test", "0.1.0")
    assert tpl.status == "published"
