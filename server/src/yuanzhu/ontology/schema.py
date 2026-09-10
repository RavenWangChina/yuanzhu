"""本体 DSL 解析器（YAML → 本体层注册格式，spec 3.2）

三类 DSL：对象类型 / 链接类型 / 动作类型。
properties 段（简写 DSL）展开为标准 JSON Schema 存库。
"""
import yaml
from typing import Any, Dict


def _require(data: Dict[str, Any], field: str) -> Any:
    if not data.get(field):
        raise ValueError(f"缺少必需字段: {field}")
    return data[field]


def _build_property_json(prop_def: Dict[str, Any]) -> Dict[str, Any]:
    """单个属性定义 → JSON Schema property 片段"""
    prop_json: Dict[str, Any] = {"type": prop_def.get("type", "string")}
    for key in ("enum", "default", "minimum", "maximum", "description"):
        if key in prop_def:
            prop_json[key] = prop_def[key]
    return prop_json


def _build_schema(properties: Dict[str, Any]) -> Dict[str, Any]:
    """properties 简写 DSL → JSON Schema"""
    schema: Dict[str, Any] = {"type": "object", "properties": {}, "required": []}
    for prop_name, prop_def in properties.items():
        schema["properties"][prop_name] = _build_property_json(prop_def)
        if prop_def.get("required", False):
            schema["required"].append(prop_name)
    return schema


def parse_object_type_yaml(yaml_content: str) -> Dict[str, Any]:
    """解析对象类型 DSL

    ```yaml
    name: Bug
    domain: aiqa
    title_key: title
    description: ...
    exposed: true
    properties:
      title: {type: string, required: true}
      status: {type: string, enum: [Open, Closed], default: Open}
    ```
    """
    data = yaml.safe_load(yaml_content)
    if not data:
        raise ValueError("YAML 内容为空")

    name = _require(data, "name")
    domain = _require(data, "domain")

    return {
        "name": name,
        "domain": domain,
        "title_key": data.get("title_key"),
        "description": data.get("description"),
        "schema_json": _build_schema(data.get("properties", {})),
        "exposed": data.get("exposed", False),
    }


def parse_link_type_yaml(yaml_content: str) -> Dict[str, Any]:
    """解析链接类型 DSL（对象类型名引用，注册期解析为 type_id）

    ```yaml
    name: has_testcase
    domain: aiqa
    source_type: Bug
    target_type: TestCase
    cardinality: many
    ```
    """
    data = yaml.safe_load(yaml_content)
    if not data:
        raise ValueError("YAML 内容为空")

    name = _require(data, "name")
    domain = _require(data, "domain")
    cardinality = data.get("cardinality", "many")
    if cardinality not in ("one", "many"):
        raise ValueError(f"cardinality 只支持 one|many，收到: {cardinality}")

    return {
        "name": name,
        "domain": domain,
        "source_type": _require(data, "source_type"),
        "target_type": _require(data, "target_type"),
        "cardinality": cardinality,
    }


def parse_action_type_yaml(yaml_content: str) -> Dict[str, Any]:
    """解析动作类型 DSL（spec 3.2 + ADR-006）

    ```yaml
    name: ChangePriority
    domain: aiqa
    description_for_agent: 修改 Bug 优先级
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
    side_effects:
      - type: notify
        target: reviewer
    ```
    """
    data = yaml.safe_load(yaml_content)
    if not data:
        raise ValueError("YAML 内容为空")

    name = _require(data, "name")
    domain = _require(data, "domain")

    autonomy_level = data.get("autonomy_level", 2)
    if not (1 <= int(autonomy_level) <= 5):
        raise ValueError(f"autonomy_level 只支持 1-5，收到: {autonomy_level}")

    return {
        "name": name,
        "domain": domain,
        "params_schema": data.get("params", {"type": "object"}),
        "submission_criteria": data.get("submission_criteria"),
        "transform": data.get("transform"),
        "side_effects": data.get("side_effects"),
        "autonomy_level": int(autonomy_level),
        "requires_staging": data.get("requires_staging", autonomy_level >= 2),
        "description_for_agent": data.get("description_for_agent"),
        "idempotency_key_template": data.get("idempotency_key_template"),
    }
