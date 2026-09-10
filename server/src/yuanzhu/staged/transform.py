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
                value = _dig(params, source_path[len("params."):])
            else:
                value = _dig(params, source_path)  # 兼容直接 params 引用
        elif "value" in rule:
            value = rule["value"]
        else:
            raise ValueError(f"transform 规则缺 from/value: {rule}")

        if target.startswith("properties."):
            _set(new_props, target[len("properties."):], value)
        else:
            raise ValueError(f"transform 目标必须在 properties 下: {target}")

    return new_props
