"""企微回调端点 + 提炼触发端点（spec 3.3；企微后台配置由管理员自助完成）

- GET  /api/dialog/wecom/callback  → URL 验证（回显 echostr）
- POST /api/dialog/wecom/callback  → 收消息（进内存缓冲，不落库）
- POST /api/dialog/refine          → 手动/定时触发提炼（缓冲 → 草稿区）

v0.1 明文模式：未配置加密参数时直接收 JSON（本地/测试用）。
配置了 YUANZHU_WECOM_TOKEN/AES_KEY 后启用验签（挂账：AES 解密通道）。
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field
from typing import Optional

from yuanzhu.db.database import get_db
from yuanzhu.dialog.buffer import message_buffer
from yuanzhu.dialog.refinement import refine_to_drafts
from yuanzhu.config import settings

router = APIRouter(prefix="/api/dialog", tags=["dialog"])


@router.get("/wecom/callback")
async def wecom_verify(msg_signature: str = "", timestamp: str = "",
                       nonce: str = "", echostr: str = ""):
    """企微回调 URL 验证：回显 echostr（明文模式）。

    启用加密后（YUANZHU_WECOM_AES_KEY 已配）：验签+解密 echostr 再回显——
    ponytail: v0.1 明文先行，AES 通道挂账（配置项已留）。
    """
    from fastapi.responses import PlainTextResponse
    if settings.wecom_aes_key:
        # M1 修复：配了 key 但验签实现未就绪 → fail-closed（拒绝而非静默明文，防虚假安全感）
        raise HTTPException(
            status_code=503,
            detail="已配置 AES key 但验签通道未实现——拒绝明文回显（挂账：AES 验签实现）",
        )
    return PlainTextResponse(echostr if echostr else "ok")


@router.post("/wecom/callback")
async def wecom_receive(request: Request):
    """收消息：JSON body（企微应用消息/群机器人转发的统一形态）→ 内存缓冲。

    合规：只处理已授权群（chat_id 白名单可配）；原文不落库。
    """
    if settings.wecom_aes_key:
        raise HTTPException(status_code=503, detail="已配置 AES key 但验签通道未实现——拒绝接收")
    try:
        message = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="消息体必须是 JSON")

    # 授权群白名单（未配置=全部接收；配置后只收白名单群）
    allowed = [c.strip() for c in settings.wecom_allowed_chats.split(",") if c.strip()]
    chat_id = (message.get("chat") or {}).get("chat_id", "")
    if allowed and chat_id and chat_id not in allowed:
        return {"ok": True, "skipped": "未授权群"}  # 静默跳过（不向企微报错）

    message_buffer.push(message)
    return {"ok": True, "buffered": len(message_buffer)}


class RefineRequest(BaseModel):
    min_messages: int = Field(default=3, ge=1)
    sample_size: int = Field(default=100, ge=1, le=2000)
    source: str = "wecom"


@router.post("/refine")
async def refine(req: RefineRequest, db: AsyncSession = Depends(get_db)):
    """提炼 job：缓冲区近 N 条 → 工作流候选 → 草稿区（status=draft）"""
    messages = message_buffer.recent(req.sample_size)
    try:
        drafts = await refine_to_drafts(
            db, messages, source=req.source, min_messages=req.min_messages
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {
        "candidates": len(drafts),
        "drafts": [
            {"id": d.id, "name": d.name, "version": d.version, "layer": d.manifest_json.get("layer")}
            for d in drafts
        ],
    }
