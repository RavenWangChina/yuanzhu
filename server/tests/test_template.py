"""模板库测试：四段式目录解析 + 注册到本体层（spec 3.2）

模板结构：manifest.yaml + ontology/{object,link}-types.yaml + actions/*.yaml
        + workflows/*.yaml + evals/cases.yaml
注册语义：ontology/actions 注册进本体层；workflows/evals 存 Template 记录。
"""
import pytest
from pathlib import Path

from yuanzhu.template.parser import parse_template_dir
from yuanzhu.template.store import TemplateStore
from yuanzhu.ontology.object_store import ObjectStore
from yuanzhu.ontology.action_store import ActionStore
from yuanzhu.ontology.link_store import LinkStore


@pytest.fixture
def minimal_template(tmp_path: Path) -> Path:
    """最小四段式模板（AIQA 的缩影）"""
    (tmp_path / "manifest.yaml").write_text("""
name: aiqa
version: 0.1.0
domain: aiqa
description: AIQA 测试工作流四段式模板
""", encoding="utf-8")

    ont = tmp_path / "ontology"
    ont.mkdir()
    (ont / "object-types.yaml").write_text("""
types:
  - name: Bug
    title_key: title
    description: 缺陷
    exposed: true
    properties:
      title: {type: string, required: true}
      status: {type: string, enum: [Open, Closed], default: Open}
      priority: {type: integer}
  - name: TestCase
    title_key: name
    description: 测试用例
    properties:
      name: {type: string, required: true}
""", encoding="utf-8")
    (ont / "link-types.yaml").write_text("""
types:
  - name: has_testcase
    source_type: Bug
    target_type: TestCase
    cardinality: many
""", encoding="utf-8")

    (tmp_path / "actions").mkdir()
    (tmp_path / "actions" / "change-priority.yaml").write_text("""
name: ChangePriority
description_for_agent: 修改 Bug 优先级（仅 Open 状态）
autonomy_level: 2
requires_staging: true
idempotency_key_template: "{object_id}-{name}"
params:
  type: object
  properties:
    object_id: {type: integer}
    priority: {type: integer}
  required: [object_id, priority]
submission_criteria:
  object_ref: params.object_id
  check: {properties.status: Open}
transform:
  - set: properties.priority
    from: params.priority
""", encoding="utf-8")

    (tmp_path / "workflows").mkdir()
    (tmp_path / "workflows" / "triage.yaml").write_text("""
name: bug-triage
description: Bug 分诊工作流
steps:
  - id: query-open
    type: action_step
    action: ChangePriority
  - id: ai-summary
    type: ai_step
    prompt_prefix: 你是 QA 专家，请总结以下缺陷列表
    model: deepseek-chat
""", encoding="utf-8")

    (tmp_path / "evals").mkdir()
    (tmp_path / "evals" / "cases.yaml").write_text("""
cases:
  - name: 改优先级-Open可通过
    steps:
      - action: ChangePriority
        params: {object_id: 1, priority: 3}
    expect: {status: applied}
""", encoding="utf-8")
    return tmp_path


# ---------- 解析 ----------

def test_parse_template_dir(minimal_template):
    parsed = parse_template_dir(minimal_template)
    assert parsed["manifest"]["name"] == "aiqa"
    assert parsed["manifest"]["version"] == "0.1.0"

    assert len(parsed["object_types"]) == 2
    assert parsed["object_types"][0]["name"] == "Bug"

    assert len(parsed["link_types"]) == 1
    assert parsed["link_types"][0]["source_type"] == "Bug"

    assert len(parsed["actions"]) == 1
    assert parsed["actions"][0]["name"] == "ChangePriority"
    assert parsed["actions"][0]["transform"] == [
        {"set": "properties.priority", "from": "params.priority"}
    ]

    assert len(parsed["workflows"]) == 1
    assert parsed["workflows"][0]["steps"][1]["type"] == "ai_step"

    assert len(parsed["evals"]) == 1


def test_parse_missing_manifest(tmp_path):
    with pytest.raises(ValueError, match="manifest"):
        parse_template_dir(tmp_path)


# ---------- 注册 ----------

async def test_register_template(db_session, minimal_template):
    store = TemplateStore(db_session)
    tpl = await store.register_dir(minimal_template)

    assert tpl.id is not None
    assert tpl.name == "aiqa"
    assert tpl.version == "0.1.0"
    assert tpl.status == "published"

    # ①对象类型已入本体层
    obj_store = ObjectStore(db_session)
    bug = await obj_store.get_type_by_name("aiqa", "Bug")
    assert bug is not None and bug.exposed is True
    assert "priority" in bug.schema_json["properties"]

    # ②链接类型已注册（名字引用解析为 type_id）
    link_store = LinkStore(db_session)
    lt = await link_store.get_type_by_name("aiqa", "has_testcase")
    assert lt.source_type_id == bug.id

    # ③动作类型已入本体层
    action_store = ActionStore(db_session)
    act = await action_store.get_type_by_name("aiqa", "ChangePriority")
    assert act.autonomy_level == 2
    assert act.submission_criteria_json["check"] == {"properties.status": "Open"}

    # ③'工作流与④评测集存在 Template 记录里
    assert len(tpl.workflows_json) == 1
    assert tpl.workflows_json[0]["name"] == "bug-triage"
    assert len(tpl.evals_json) == 1


async def test_register_idempotent(db_session, minimal_template):
    """同模板重复注册 = upsert，不产生重复记录"""
    store = TemplateStore(db_session)
    t1 = await store.register_dir(minimal_template)
    t2 = await store.register_dir(minimal_template)
    assert t2.id == t1.id

    # 本体层也只有一份
    obj_store = ObjectStore(db_session)
    types = await obj_store.list_types(domain="aiqa")
    assert len(types) == 2  # Bug + TestCase，无重复
