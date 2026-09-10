"""TransformEngine：通用确定性转换规则引擎（消除 Golden Hammer）

规则结构（存储在 ActionType.transform_json）：
    [{"set": "properties.priority", "from": "params.priority"}]

语义：
- "set"：目标路径，相对对象根。properties.x → obj.properties_json["x"]
- "from"：来源路径。params.x → 动作参数，或字面量
- 可选 "value"：字面量值（与 from 二选一）

动作执行逻辑由数据驱动，不在代码中硬编码动作名——
新增确定性动作只加 transform 规则，不改引擎（元流程反模式核验：确定性转换不用 AI）。
"""
import copy
from typing import Any, Dict, List


def _dig(data: Dict[str, Any], path: str) -> Any:
    node: Any = data
    for part in path.split("."):
        if not isinstance(node, dict) or part not in node:
            raise KeyError(f"路径不存在: {path}")
        node = node[part]
    return node


def _set(obj_properties: Dict[str, Any], path: str, value: Any) -> None:
    """在 properties 内按路径赋值（支持一层嵌套：properties.a.b）"""
    parts = path.split(".")
    node = obj_properties
    for part in parts[:-1]:
        node = node.setdefault(part, {})
    node[parts[-1]] = value


def apply_transform(
    rules: List[Dict[str, Any]],
    params: Dict[str, Any],
    object_properties: Dict[str, Any],
) -> Dict[str, Any]:
    """对对象属性应用转换规则，返回新属性（不修改入参）

    返回值 = 原属性的深拷贝 + 规则赋值。
    """
    if not rules:
        return copy.deepcopy(object_properties)

    new_props = copy.deepcopy(object_properties)
    for rule in rules:
        target = rule.get("set")
        if not target:
            raise ValueError(f"transform 规则缺 set: {rule}")

        if "from" in rule:
            source_path = rule["from"]
            if source_path.startswith("params."):
                source_path = source_path[len("params."):]
            # 可选参数缺失 → 跳过该 set（params_schema 的 required 才是必填裁决）
            node: Any = params
            for part in source_path.split("."):
                if not isinstance(node, dict) or part not in node:
                    node = None
                    break
                node = node[part]
            if node is None:
                continue
            value = node
        elif "value" in rule:
            value = rule["value"]
        else:
            raise ValueError(f"transform 规则缺 from/value: {rule}")

        if target.startswith("properties."):
            _set(new_props, target[len("properties."):], value)
        else:
            raise ValueError(f"transform 目标必须在 properties 下: {target}")

    return new_props


def resolve_with_value(spec: str, params: Dict[str, Any]) -> Any:
    """create_object 的 with 值解析：from:params.x / literal:v / 裸值

    from 引用的可选参数缺失时返回 None（属性留空），不炸——
    params_schema 的 required 才是必填的裁决点。
    """
    if not isinstance(spec, str):
        return spec
    if spec.startswith("from:params."):
        node: Any = params
        for part in spec[len("from:params."):].split("."):
            if not isinstance(node, dict):
                return None
            node = node.get(part)
        return node
    if spec.startswith("literal:"):
        return spec[len("literal:"):]
    return spec
