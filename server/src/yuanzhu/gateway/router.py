"""模型网关 REST：OpenAI 兼容端点（/v1/chat/completions、/v1/models）+ 计量落库"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List
from pydantic import BaseModel, Field

from yuanzhu.db.database import get_db
from yuanzhu.gateway.proxy import acompletion, extract_usage, build_usage_record

router = APIRouter(prefix="/v1", tags=["gateway"])



class ChatMessage(BaseModel):
    role: str
    content: str


class ChatCompletionRequest(BaseModel):
    model: str
    messages: List[ChatMessage]
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    # 计量上下文（非 OpenAI 标准字段，网关剥离后转发）
    metadata: Optional[dict] = Field(default=None)


@router.post("/chat/completions")
async def chat_completions(body: ChatCompletionRequest, db: AsyncSession = Depends(get_db)):
    meta = body.metadata or {}
    forward = body.model_dump(exclude={"metadata"}, exclude_none=True)
    try:
        response = await acompletion(**forward)
    except Exception as e:
        # 降级兜底附上下文（DMLA：不带上下文的兜底=二次浪费）
        raise HTTPException(
            status_code=502,
            detail=f"模型网关上游失败（model={body.model}）: {e}",
        )

    usage = extract_usage(response)
    record = build_usage_record(
        model=body.model, usage=usage,
        task_id=meta.get("task_id"), caller=meta.get("caller", "unknown"),
    )
    db.add(record)

    return response if isinstance(response, dict) else response.model_dump()


@router.get("/models")
async def list_models():
    """动态：来自 ProviderRegistry（dsh 导入 + .env 自定义 + 内置兜底的并集）"""
    from yuanzhu.gateway.providers import get_registry
    return {"object": "list", "data": [{"id": m, "object": "model"} for m in get_registry().models]}
