"""forge 测试：一句话描述 → AI 生成四段式 → evals 守门 → 上架/留草稿"""
import pytest
from pathlib import Path

from yuanzhu.template.forge import forge_template
from yuanzhu.template.store import TemplateStore

from yuanzhu.template.forge import FORGE_ROOT   # v0.2：用户目录（单一真源）


@pytest.fixture(autouse=True)
def cleanup_forge():
    """每用例后清 forge 产物目录（测试隔离）"""
    import shutil
    yield
    shutil.rmtree(FORGE_ROOT, ignore_errors=True)


GOOD_TEMPLATE = {
    "manifest": {
        "name": "forge-test", "version": "0.1.0", "domain": "forgetest",
        "description": "forge 测试域",
    },
    "object_types": [
        {"name": "Task", "title_key": "title", "exposed": True,
         "properties": {"title": {"type": "string", "required": True},
                        "status": {"type": "string", "enum": ["Open", "Done"], "default": "Open"}}},
    ],
    "link_types": [],
    "actions": [
        {"name": "CreateTask", "description_for_agent": "创建任务（进待审）",
         "autonomy_level": 2, "requires_staging": True,
         "params": {"type": "object", "properties": {"title": {"type": "string"}},
                    "required": ["title"]},
         "transform": [{"create_object": {"type": "Task"},
                        "with": {"title": "from:params.title", "status": "literal:Open"}}]},
    ],
    "workflows": [
        {"name": "add-task", "description": "添加任务（人审）",
         "params_schema": [{"name": "title", "label": "任务标题", "type": "string", "required": True}],
         "steps": [{"id": "submit", "type": "action_step", "action": "CreateTask",
                    "params": {"title": "$params.title"}}]},
    ],
    "evals": [
        {"name": "建任务-人审入库",
         "steps": [{"action": "CreateTask", "params": {"title": "eval-t1"},
                    "expect": {"status": "staged"}},
                   {"approve": {}}],
         "expect": {"status": "applied", "object_exists": {"type": "Task", "title": "eval-t1"}}},
    ],
}


async def test_forge_publishes_when_evals_pass(db_session, monkeypatch):
    """evals 全过 → 自动上架 published（AI 铸、evals 守门）"""
    import yuanzhu.template.forge as forge_mod
    async def fake_gen(description):
        return dict(GOOD_TEMPLATE)
    monkeypatch.setattr(forge_mod, "generate_template_json", fake_gen)

    result = await forge_template(db_session, "管理每日待办任务")

    assert result["status"] == "published"
    assert result["evals"]["passed"] == result["evals"]["total"] == 1
    # 目录已生成（可人工微调）
    assert (FORGE_ROOT / "forge-test" / "manifest.yaml").is_file()
    assert (FORGE_ROOT / "forge-test" / "evals" / "cases.yaml").is_file()
    # 模板市场可见且可运行
    store = TemplateStore(db_session)
    tpl = await store.get_by_name_version("forge-test", "0.1.0")
    assert tpl.status == "published"
    assert tpl.workflows_json[0]["name"] == "add-task"


async def test_forge_keeps_draft_when_evals_fail(db_session, monkeypatch):
    """evals 不过 → 留在草稿区 + 失败报告（人可修目录后重注册）"""
    import yaml
    import yuanzhu.template.forge as forge_mod

    # 坏法：eval 期望 staged，但动作是 L1 自动执行（引用一致性过校验、运行期才暴露）
    bad = dict(GOOD_TEMPLATE)
    bad["actions"] = [dict(GOOD_TEMPLATE["actions"][0],
                           autonomy_level=1, requires_staging=False)]

    async def fake_gen(description):
        return dict(bad)
    monkeypatch.setattr(forge_mod, "generate_template_json", fake_gen)

    result = await forge_template(db_session, "管理每日待办任务")
    assert result["status"] == "draft"
    assert result["evals"]["failed"] >= 1

    store = TemplateStore(db_session)
    tpl = await store.get_by_name_version("forge-test", "0.1.0")
    assert tpl.status == "draft"


async def test_forge_requires_evals(db_session, monkeypatch):
    """硬规则：AI 生成缺 evals → 直接拒（无 evals 不上架）"""
    import yuanzhu.template.forge as forge_mod
    no_evals = dict(GOOD_TEMPLATE)
    no_evals["evals"] = []

    async def fake_gen(description):
        return dict(no_evals)
    monkeypatch.setattr(forge_mod, "generate_template_json", fake_gen)

    with pytest.raises(ValueError, match="evals"):
        await forge_template(db_session, "描述")
