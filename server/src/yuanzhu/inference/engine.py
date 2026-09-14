"""推衍引擎：基于三记忆系统交叉分析，产出主动提议"""
import json
from pathlib import Path
from typing import Any, Dict, List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from yuanzhu.db.models import BehaviorLog, ObjectType, Object, Template, Base, utcnow
from sqlalchemy import Column, Integer, String, Text, JSON, DateTime, Float


class Proposition(Base):
    """主动提议（推衍引擎的产出）"""
    __tablename__ = "proposition"

    id = Column(Integer, primary_key=True, autoincrement=True)
    prop_type = Column(String(50), nullable=False, index=True)  # workflow_suggestion / knowledge_gap / pattern_insight / procedural_hint
    insight = Column(Text, nullable=False)       # 推衍结论（给用户看的一句话）
    advice = Column(Text, nullable=True)          # 建议行动
    deliverable_draft = Column(JSON, nullable=True)  # 交付物草稿（如 forge description）
    confidence = Column(Float, default=0.5)
    status = Column(String(50), default="pending", index=True)  # pending / accepted / dismissed
    created_at = Column(DateTime, default=utcnow, nullable=False)
    resolved_at = Column(DateTime, nullable=True)


# 推衍 prompt（稳定前缀——缓存友好）
INFER_PROMPT_PREFIX = """你是行为意图推衍师。基于用户的三记忆系统（行为日志/知识库/技能库），交叉分析并产出主动提议。

三记忆系统数据：
"""

INFER_PROMPT_SUFFIX = """

你的任务：
1. 行为模式识别：用户最近在做什么方向的尝试？有什么重复模式？
2. 知识缺口发现：已有知识中有什么可以组合但尚未组合的？
3. 技能匹配：用户在重复做某件事，但已有工作流可以帮他？
4. 超预期提议：比用户自己能想到的更有价值的下一步。

严格按 JSON 数组输出（最多 3 条），每项：
{"type": "workflow_suggestion|knowledge_gap|pattern_insight|procedural_hint",
 "insight": "一句话推衍结论（给用户看）",
 "advice": "建议行动",
 "deliverable_draft": "如果是workflow_suggestion，给一段forge描述",
 "confidence": 0.0-1.0}

如果数据不足以推衍出有价值的提议，输出 []。
只输出 JSON，不要其他文字。"""


async def run_inference(session: AsyncSession) -> List[Dict[str, Any]]:
    """推衍引擎：收集三记忆系统数据 → AI 交叉分析 → 产出 Proposition"""
    from yuanzhu.workflow.engine import call_model
    import yuanzhu.config as cfg

    # 收集数据（体量约束——防 prompt 爆炸）
    behaviors = (await session.execute(
        select(BehaviorLog).order_by(BehaviorLog.created_at.desc()).limit(100)
    )).scalars().all()

    insight_type = (await session.execute(
        select(ObjectType).where(ObjectType.domain == "metaflow", ObjectType.name == "Insight")
    )).scalar_one_or_none()
    insights = []
    if insight_type:
        objs = (await session.execute(
            select(Object).where(Object.type_id == insight_type.id).limit(50)
        )).scalars().all()
        insights = [
            {"takeaway": (o.properties or {}).get("takeaway", ""),
             "context": (o.properties or {}).get("context", "")}
            for o in objs if (o.properties or {}).get("takeaway")
        ]

    templates = (await session.execute(
        select(Template).where(Template.status == "published")
    )).scalars().all()
    template_summaries = [
        {"name": t.name, "description": (t.manifest_json or {}).get("description", ""),
         "workflow_count": len(t.workflows_json or [])}
        for t in templates
    ]

    # 数据不足时不推衍
    if len(behaviors) < 3 and len(insights) < 2:
        return []

    # 组装 prompt
    behavior_data = [
        {"action": b.action, "actor": b.actor,
         "target": b.target_name, "detail": b.detail_json}
        for b in behaviors
    ]

    prompt = (
        INFER_PROMPT_PREFIX
        + f"\n行为日志（最近{len(behaviors)}条）：\n{json.dumps(behavior_data, ensure_ascii=False, default=str)}\n"
        + f"\n知识库洞见（{len(insights)}条）：\n{json.dumps(insights, ensure_ascii=False)}\n"
        + f"\n已有技能/模板（{len(template_summaries)}个）：\n{json.dumps(template_summaries, ensure_ascii=False)}\n"
        + INFER_PROMPT_SUFFIX
    )

    # 调 AI
    content = await call_model("glm-5.1", prompt, caller="inference")
    propositions_data = _parse_json_array(content)

    # 产出 Proposition
    results = []
    for prop in propositions_data[:3]:
        p = Proposition(
            prop_type=prop.get("type", "pattern_insight"),
            insight=prop.get("insight", ""),
            advice=prop.get("advice"),
            deliverable_draft=prop.get("deliverable_draft"),
            confidence=float(prop.get("confidence", 0.5)),
        )
        session.add(p)
        results.append({
            "type": p.prop_type, "insight": p.insight,
            "advice": p.advice, "confidence": p.confidence,
        })

    await session.flush()
    return results


def _parse_json_array(content: str) -> List[Dict]:
    import re
    text = content.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
    start, end = text.find("["), text.rfind("]")
    if start == -1 or end <= start:
        return []
    try:
        return json.loads(text[start:end + 1])
    except:
        return []
