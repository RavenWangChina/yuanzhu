"""forge：一句话铸模板（冷启动核心能力——把"模板开发"变成"说人话"）

流程：用户描述工作场景 → AI 生成四段式模板 JSON → 落盘 templates/forge/<name>/
→ 注册（draft）→ EvalsRunner 验证 → 全过自动上架（AI 铸、evals 守门、人最后看）。
"""
import json
import re
from pathlib import Path
from typing import Any, Dict, List

import yaml

# v0.2：forge 产物写用户数据目录（site-packages 不可写）；包内 templates 只读
from pathlib import Path as _P
USER_TEMPLATES = _P.home() / ".yuanzhu" / "templates"
FORGE_ROOT = USER_TEMPLATES / "forge"

# 稳定前缀：四段式生成规范（few-shot 片段取自真实模板）
FORGE_PROMPT_PREFIX = """你是工作流模板架构师。把用户描述的工作场景铸成"四段式模板"。

严格按以下 JSON 结构输出（不要任何其他文字）：
{
  "manifest": {"name": "小写英文域名", "version": "0.1.0", "domain": "同name", "description": "一句话中文描述"},
  "object_types": [
    {"name": "PascalCase名", "title_key": "标题属性名", "exposed": true,
     "description": "中文说明",
     "properties": {"属性名": {"type": "string|integer", "required": false,
                   "enum": ["..."], "default": "..."}}}
  ],
  "link_types": [],
  "actions": [
    {"name": "CreateXxx / CompleteXxx", "description_for_agent": "中文动作说明",
     "autonomy_level": 2, "requires_staging": true,
     "idempotency_key_template": "xxx-{title}",
     "params": {"type": "object", "properties": {"title": {"type": "string"}}, "required": ["title"]},
     "transform": [{"create_object": {"type": "对象名"},
                    "with": {"title": "from:params.title", "status": "literal:Open"}}]}
  ],
  "workflows": [
    {"name": "小写短横线名", "description": "中文描述",
     "params_schema": [{"name": "参数名", "label": "中文标签", "type": "string|text",
                        "required": true, "placeholder": "示例"}],
     "steps": [{"id": "submit", "type": "action_step", "action": "动作名",
                "params": {"title": "$params.参数名"}}]}
  ],
  "evals": [
    {"name": "中文用例名",
     "steps": [{"action": "动作名", "params": {"title": "eval-测试值"},
                "expect": {"status": "staged"}},
               {"approve": {}}],
     "expect": {"status": "applied", "object_exists": {"type": "对象名", "title": "eval-测试值"}}}
  ]
}

设计规则：
- 对象 2-3 个够用（少而精）；每个意图只一个动作，动作名与对象对齐（对象 GroupReport → 动作 CreateGroupReport，不要 CreateDeptReport/CreateDepartmentReport 同义重复）
- 写操作默认 autonomy_level 2 人审；低风险纯登记可 1+requires_staging false（自动生效）
- evals 必须至少 1 条，且 params 的 title 用 "eval-" 前缀（避免幂等键冲突）
- evals 一致性：只引用已声明的动作名；object_exists.type 必须与动作 transform 的 create_object.type 逐字一致；
  L1 动作的 eval expect status=applied（无 approve 步）；L2 动作 expect status=staged 后接 approve 步
- transform 的 with 值：from:params.属性 / literal:固定值；with 引用的属性必须在 params.properties 里声明
- 工作流步骤三选一：action_step（做动作）/ ai_step（AI 处理，prompt_prefix+prompt_var+model glm-5.1+expect_json）/ query_step（查对象）"""


async def generate_template_json(description: str) -> Dict[str, Any]:
    """调模型生成模板 JSON（测试被 monkeypatch 替换）"""
    from yuanzhu.workflow.engine import call_model
    content = await call_model(
        "glm-5.1",
        FORGE_PROMPT_PREFIX + "\n\n用户场景描述：\n" + description,
        caller="forge",
    )
    return _parse_json(content)


async def forge_template(session, description: str) -> Dict[str, Any]:
    """一句话 → 四段式模板 → evals 守门 → 上架/草稿"""
    template = await generate_template_json(description)
    _validate(template)

    name = template["manifest"]["name"]
    tpl_dir = _write_files(name, template)

    from yuanzhu.template.store import TemplateStore
    store = TemplateStore(session)
    tpl = await store.register_dir(tpl_dir, status="draft")  # 先入草稿（硬规则：无守门不上架）

    status, report = await _gate_on_evals(session, tpl)
    return {
        "name": name, "status": status, "directory": str(tpl_dir),
        "evals": _report_summary(report),
    }


async def reload_template(session, name: str) -> dict:
    """T6 草稿转正：重读 templates/forge/<name>/ 目录（人工修正后）
    → 重注册（保持 draft）→ 重跑 evals 守门 → 全过升级 published。"""
    tpl_dir = FORGE_ROOT / name
    if not (tpl_dir / "manifest.yaml").is_file():
        raise ValueError(f"模板目录不存在: {tpl_dir}")

    from yuanzhu.template.store import TemplateStore
    from sqlalchemy import select
    from yuanzhu.db.models import Template
    result = await session.execute(select(Template).where(Template.name == name))
    existing = result.scalar_one_or_none()
    version = existing.version if existing else "0.1.0"

    store = TemplateStore(session)
    tpl = await store.register_dir(tpl_dir, status="draft")  # 审查提示：必须显式 draft，防跳守门
    status, report = await _gate_on_evals(session, tpl)
    return {"name": name, "status": status, "directory": str(tpl_dir),
            "evals": _report_summary(report)}


async def _gate_on_evals(session, tpl) -> tuple:
    """evals 守门（forge/reload 共用）：跑当前域 draft 模板评测，全过升级 published；
    报告摘要存 manifest_json.last_evals_report（Web 显示失败原因）。"""
    from yuanzhu.evals.runner import EvalsRunner
    report = await EvalsRunner(session).run_template(tpl.domain, status="draft")

    if report["total"] > 0 and report["failed"] == 0:
        tpl.status = "published"

    manifest = dict(tpl.manifest_json or {})
    manifest["last_evals_report"] = _report_summary(report)
    tpl.manifest_json = manifest
    await session.flush()

    status = "published" if tpl.status == "published" else "draft"
    return status, report


def _report_summary(report: dict) -> dict:
    return {"total": report["total"], "passed": report["passed"],
            "failed": report["failed"],
            "failures": [c["name"] for c in report["cases"] if not c["ok"]]}


# ---------- 校验与落盘 ----------

def _validate(t: Dict[str, Any]) -> None:
    for section in ("manifest", "object_types", "actions", "workflows", "evals"):
        if section not in t:
            raise ValueError(f"AI 生成的模板缺少段: {section}（请重试或换种描述）")
    if not t["evals"]:
        raise ValueError("AI 生成的模板没有 evals——无评测不上架（硬规则）")
    name = t["manifest"].get("name", "")
    if not re.fullmatch(r"[a-z][a-z0-9-]{1,30}", name):
        raise ValueError(f"模板域名不合法（需小写英文）: {name!r}")

    # 一致性校验（实测发现的 AI 生成物系统性缺陷：引用未声明的动作/类型）
    action_names = {a["name"] for a in t["actions"]}
    declared_types = {o["name"] for o in t["object_types"]}
    created_types = set()
    for a in t["actions"]:
        for rule in a.get("transform") or []:
            if "create_object" in rule:
                created_types.add(rule["create_object"].get("type"))
    for case in t["evals"]:
        for step in case.get("steps", []):
            act = step.get("action")
            if act and act not in action_names:
                raise ValueError(f"evals 引用了未声明的动作: {act}（可用: {sorted(action_names)}）")
        obj = (case.get("expect") or {}).get("object_exists") or {}
        if obj.get("type") and obj["type"] not in created_types:
            raise ValueError(
                f"evals 的 object_exists.type {obj['type']!r} 无对应 create_object 动作"
                f"（动作建的类型: {sorted(created_types)}）")


def _write_files(name: str, template: Dict[str, Any]) -> Path:
    """模板 JSON → 四段式目录（可人工微调后再注册）"""
    tpl_dir = FORGE_ROOT / name
    (tpl_dir / "ontology").mkdir(parents=True, exist_ok=True)
    (tpl_dir / "actions").mkdir(exist_ok=True)
    (tpl_dir / "workflows").mkdir(exist_ok=True)
    (tpl_dir / "evals").mkdir(exist_ok=True)

    _yaml_dump(tpl_dir / "manifest.yaml", template["manifest"])
    _yaml_dump(tpl_dir / "ontology" / "object-types.yaml",
               {"types": template["object_types"]})
    _yaml_dump(tpl_dir / "ontology" / "link-types.yaml",
               {"types": template.get("link_types") or []})
    for action in template["actions"]:
        safe = re.sub(r"[^a-z0-9-]", "-", action["name"].lower()).strip("-")
        _yaml_dump(tpl_dir / "actions" / f"{safe}.yaml", action)
    for wf in template["workflows"]:
        _yaml_dump(tpl_dir / "workflows" / f"{wf['name']}.yaml", wf)
    _yaml_dump(tpl_dir / "evals" / "cases.yaml", {"cases": template["evals"]})
    return tpl_dir


def _yaml_dump(path: Path, data: Any) -> None:
    path.write_text(
        yaml.dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")


def _parse_json(content: str) -> Dict[str, Any]:
    """宽容解析：剥代码栅栏、截取最外层 {}"""
    text = content.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        raise ValueError(f"AI 输出不含 JSON 对象: {content[:80]}")
    return json.loads(text[start:end + 1])
