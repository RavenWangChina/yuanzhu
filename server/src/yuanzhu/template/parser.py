"""四段式模板解析器（spec 3.2）

目录结构：
    manifest.yaml                     # name/version/domain/description
    ontology/object-types.yaml        # {types: [{name, properties, ...}]}
    ontology/link-types.yaml          # {types: [{name, source_type, target_type}]}
    actions/*.yaml                    # 每文件一个动作（parse_action_type_yaml 格式）
    workflows/*.yaml                  # 每文件一个工作流（steps: action_step|ai_step|transform_step）
    evals/cases.yaml                  # {cases: [...]}
"""
from pathlib import Path
from typing import Any, Dict, List

import yaml

from yuanzhu.ontology.schema import parse_action_type_yaml, _build_schema


def _load_yaml(path: Path) -> Any:
    if not path.exists():
        return None
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def parse_template_dir(template_dir: Path) -> Dict[str, Any]:
    """模板目录 -> 注册指令集（纯解析，无写操作）"""
    template_dir = Path(template_dir)
    manifest = _load_yaml(template_dir / "manifest.yaml")
    if not manifest:
        raise ValueError(f"缺少或空的 manifest: {template_dir / 'manifest.yaml'}")

    for field in ("name", "version", "domain"):
        if not manifest.get(field):
            raise ValueError(f"manifest 缺少必需字段: {field}")

    domain = manifest["domain"]

    object_types: List[Dict[str, Any]] = []
    raw_objects = _load_yaml(template_dir / "ontology" / "object-types.yaml") or {}
    for item in raw_objects.get("types", []):
        object_types.append({
            "name": item["name"],
            "domain": domain,
            "title_key": item.get("title_key"),
            "description": item.get("description"),
            "schema_json": _build_schema(item.get("properties", {})),
            "exposed": item.get("exposed", False),
        })

    link_types: List[Dict[str, Any]] = []
    raw_links = _load_yaml(template_dir / "ontology" / "link-types.yaml") or {}
    for item in raw_links.get("types", []):
        link_types.append({
            "name": item["name"],
            "domain": domain,
            "source_type": item["source_type"],
            "target_type": item["target_type"],
            "cardinality": item.get("cardinality", "many"),
        })

    actions: List[Dict[str, Any]] = []
    actions_dir = template_dir / "actions"
    if actions_dir.exists():
        for f in sorted(actions_dir.glob("*.yaml")):
            parsed = parse_action_type_yaml(f.read_text(encoding="utf-8"))
            parsed["domain"] = domain  # manifest 域为权威
            actions.append(parsed)

    workflows: List[Dict[str, Any]] = []
    wf_dir = template_dir / "workflows"
    if wf_dir.exists():
        for f in sorted(wf_dir.glob("*.yaml")):
            data = _load_yaml(f)
            if data:
                workflows.append(data)

    raw_evals = _load_yaml(template_dir / "evals" / "cases.yaml") or {}
    evals: List[Dict[str, Any]] = raw_evals.get("cases", [])

    return {
        "manifest": manifest,
        "object_types": object_types,
        "link_types": link_types,
        "actions": actions,
        "workflows": workflows,
        "evals": evals,
    }
