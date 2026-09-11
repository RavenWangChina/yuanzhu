"""AIQA 真模板（templates/aiqa/）注册测试——四段式①②真数据走通"""
from pathlib import Path

import pytest

from yuanzhu.template.parser import parse_template_dir
from yuanzhu.template.store import TemplateStore
from yuanzhu.ontology.object_store import ObjectStore
from yuanzhu.ontology.action_store import ActionStore
from yuanzhu.ontology.link_store import LinkStore

AIQA_DIR = Path(__import__("yuanzhu.__init__", fromlist=["__file__"]).__file__).parent / "templates" / "aiqa"


def test_aiqa_template_parses():
    parsed = parse_template_dir(AIQA_DIR)

    assert parsed["manifest"]["name"] == "aiqa"
    # ① 5 对象类型
    names = {o["name"] for o in parsed["object_types"]}
    assert names == {"Module", "TestCase", "Bug", "Evidence", "Report"}
    # ①' 4 链接类型
    assert len(parsed["link_types"]) == 4
    # ② 6 动作
    action_names = {a["name"] for a in parsed["actions"]}
    assert action_names == {
        "RegisterModule", "CreateBug", "ResolveBug",
        "CreateTestCase", "LinkEvidence", "CreateReport",
    }
    # ③ 2 工作流
    wf_names = {w["name"] for w in parsed["workflows"]}
    assert wf_names == {"archaeology", "test-report"}
    # ④ 评测用例
    assert len(parsed["evals"]) == 3


async def test_aiqa_template_registers(db_session):
    store = TemplateStore(db_session)
    tpl = await store.register_dir(AIQA_DIR)

    assert tpl.name == "aiqa"
    assert tpl.status == "published"

    obj_store = ObjectStore(db_session)
    types = await obj_store.list_types(domain="aiqa")
    assert len(types) == 5  # 五对象类型无重复

    # exposed 的类型可被 MCP 查询（Module/TestCase/Bug/Report）
    exposed = [t for t in types if t.exposed]
    assert {t.name for t in exposed} == {"Module", "TestCase", "Bug", "Report"}

    # 动作自主性：RegisterModule L1，其余 L2（读高写低）
    action_store = ActionStore(db_session)
    actions = await action_store.list_types(domain="aiqa")
    by_name = {a.name: a for a in actions}
    assert by_name["RegisterModule"].autonomy_level == 1
    assert by_name["RegisterModule"].requires_staging is False
    assert by_name["CreateBug"].autonomy_level == 2
    assert by_name["CreateBug"].requires_staging is True

    # 链接类型的 type_id 已解析
    link_store = LinkStore(db_session)
    bug_type = await obj_store.get_type_by_name("aiqa", "Bug")
    reproduced = await link_store.get_type_by_name("aiqa", "reproduced_by")
    assert reproduced.source_type_id == bug_type.id

    # 幂等重注册
    tpl2 = await store.register_dir(AIQA_DIR)
    assert tpl2.id == tpl.id
    assert len(await obj_store.list_types(domain="aiqa")) == 5
