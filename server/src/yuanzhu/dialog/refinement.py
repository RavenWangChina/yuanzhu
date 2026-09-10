"""对话学习提炼 job（spec 3.3 + ADR-007 + ADR-008）

流程：取近 N 条消息 → 模型提炼「高频工作模式候选」 → 候选落 Template 草稿区（draft）
诚实边界：候选 manifest 标注 layer=协同层（H4 边界试验的数据燃料）
提示词分区（ADR-008）：稳定前缀（提炼规则）+ 可变段（消息样本）
"""
import json
from typing import Any, Dict, List

from sqlalchemy.ext.asyncio import AsyncSession

from yuanzhu.db.models import Template

# 稳定前缀：提炼规则（缓存友好，改规则=改前缀=版本升级）
REFINE_PROMPT_PREFIX = """你是企业工作流分析师。分析以下企业 IM 群的消息样本，提炼「高频工作模式候选」：
- 谁经常要什么（角色-需求对）
- 什么请求反复出现（≥2 次即算高频）
- 什么流程被重复描述

严格按 JSON 数组输出，每项：
{"name": "工作流名", "description": "模式描述（谁/何时/要什么）",
 "trigger": "触发条件", "steps_draft": ["步骤1", "步骤2"],
 "layer": "协同层"}

layer 只能填「协同层」（诚实边界：对话学习预期承载协同层，领域知识走专家线）。
只输出 JSON 数组，不要其他文字。提炼不出就输出 []。"""


async def call_model(prompt: str, model: str = "glm-5.1", session=None) -> str:
    """经模型网关调用（测试被 monkeypatch 替换；session 透传做计量 I4）"""
    from yuanzhu.workflow.engine import call_model as _call
    return await _call(model, prompt, session=session, caller="dialog-refine")


async def refine_to_drafts(
    session: AsyncSession,
    messages: List[Dict[str, Any]],
    source: str = "default",
    min_messages: int = 3,
) -> List[Template]:
    """提炼消息样本 → 候选模板（status=draft 进草稿区，人审后四段式化上架）"""
    if len(messages) < min_messages:
        raise ValueError(f"消息不足（{len(messages)} < {min_messages}），样本太少不提炼（防噪音）")

    # 可变段：消息样本（发送者/群/内容/时间）序列化
    sample = [
        {
            "who": (m.get("from") or {}).get("name", "?"),
            "chat": (m.get("chat") or {}).get("name", "?"),
            "text": (m.get("text") or {}).get("content", ""),
            "ts": m.get("timestamp"),
        }
        for m in messages
    ]
    prompt = REFINE_PROMPT_PREFIX + "\n\n消息样本：\n" + json.dumps(sample, ensure_ascii=False)

    content = await call_model(prompt, session=session)
    candidates = _parse_json_array(content)

    drafts = []
    for cand in candidates:
        draft = await _upsert_draft(session, cand, source)
        drafts.append(draft)
    return drafts


async def _upsert_draft(session: AsyncSession, cand: Dict[str, Any], source: str) -> Template:
    """候选 → Template 草稿（name 幂等 upsert；version 用日期轮次）"""
    from datetime import datetime, timezone
    from sqlalchemy import select

    name = cand["name"]
    version = datetime.now(timezone.utc).strftime("draft-%Y%m%d%H%M")
    result = await session.execute(
        select(Template).where(Template.name == name, Template.status == "draft")
    )
    tpl = result.scalar_one_or_none()
    if not tpl:
        tpl = Template(name=name, version=version, domain="dialog-learned")
        session.add(tpl)

    tpl.domain = "dialog-learned"
    tpl.status = "draft"
    tpl.version = version
    tpl.manifest_json = {
        "name": name,
        "description": cand.get("description"),
        "source": "对话学习",
        "source_group": source,
        "layer": cand.get("layer", "协同层"),  # 诚实边界标注
        "trigger": cand.get("trigger"),
    }
    tpl.workflows_json = [{
        "name": name,
        "description": cand.get("description"),
        "steps": [{"id": f"draft-{i+1}", "type": "draft_step", "desc": s}
                  for i, s in enumerate(cand.get("steps_draft") or [])],
    }]
    tpl.evals_json = []  # 人审四段式化时补（硬规则：无 evals 不上架）
    await session.flush()
    await session.refresh(tpl)
    return tpl


def _parse_json_array(content: str) -> List[Dict[str, Any]]:
    """宽容解析（与 WorkflowEngine._parse_json_array 同策略）"""
    text = content.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
    start, end = text.find("["), text.rfind("]")
    if start == -1 or end <= start:
        return []
    return json.loads(text[start:end + 1])
