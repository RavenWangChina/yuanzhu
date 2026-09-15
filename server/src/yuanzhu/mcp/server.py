"""MCP Streamable HTTP 端点（标准 MCP：initialize 握手 + tools/list + tools/call）

v0.1.9 前是 JSON-RPC 风格子集（无握手）——标准 MCP 客户端（Claude Code 等）连不上。
现按 MCP Streamable HTTP 规范实现无状态子集：
- POST initialize → serverInfo（无 session，不返回 mcp-session-id）
- POST notifications/* → 202
- POST tools/list | tools/call → JSON-RPC result 包装（content: [{type: text}]）
- GET /mcp → 405（服务端无主动推送，规范允许）
"""
import json

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from yuanzhu.db.database import get_db
from yuanzhu.mcp.tools import MCPToolGenerator
from yuanzhu.mcp.handlers import MCPHandlers
from yuanzhu import __version__

router = APIRouter(tags=["mcp"])

PROTOCOL_VERSION = "2025-03-26"

# 规范版本协商：回显客户端版本（若已知），否则用我们支持的
KNOWN_VERSIONS = {"2024-11-05", "2025-03-26", "2025-06-18"}


def _rpc_ok(req_id, result) -> JSONResponse:
    return JSONResponse({"jsonrpc": "2.0", "id": req_id, "result": result})


def _rpc_err(req_id, code: int, message: str) -> JSONResponse:
    return JSONResponse({"jsonrpc": "2.0", "id": req_id,
                         "error": {"code": code, "message": message}})


@router.get("/mcp")
async def mcp_sse():
    """无状态实现：不提供服务端推送流（规范允许 405）。"""
    return JSONResponse({"error": "此端点仅支持 POST（Streamable HTTP 无推送模式）"},
                        status_code=405)


@router.post("/mcp")
async def handle_mcp(request: Request, db: AsyncSession = Depends(get_db)):
    body = await request.json()
    method = body.get("method")
    req_id = body.get("id")
    params = body.get("params", {}) or {}
    agent_id = request.headers.get("X-Agent-ID", "unknown-agent")

    # notification（无 id）：initialized / cancelled 等一律静默接受
    if req_id is None:
        return JSONResponse(None, status_code=202)

    if method == "initialize":
        client_ver = (params.get("protocolVersion") or "").strip()
        return _rpc_ok(req_id, {
            "protocolVersion": client_ver if client_ver in KNOWN_VERSIONS else PROTOCOL_VERSION,
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "yuanzhu", "version": __version__},
        })

    if method == "ping":
        return _rpc_ok(req_id, {})

    if method == "tools/list":
        tools = await MCPToolGenerator(db).list_tools()
        return _rpc_ok(req_id, {"tools": tools})

    if method == "tools/call":
        tool_name = params.get("name", "")
        arguments = params.get("arguments", {}) or {}
        handlers = MCPHandlers(db)

        if tool_name.startswith("query_"):
            result = await handlers.handle_query(tool_name, arguments)
        elif tool_name.startswith("execute_"):
            result = await handlers.handle_execute(tool_name, arguments, agent_id)
        elif tool_name == "templates_list":
            result = await handlers.handle_templates_list(arguments)
        elif tool_name == "list_pending_approvals":
            result = await handlers.handle_list_pending(arguments)
        elif tool_name == "approve_action":
            result = await handlers.handle_approve(arguments, agent_id)
        elif tool_name == "reject_action":
            result = await handlers.handle_reject(arguments, agent_id)
        else:
            return _rpc_ok(req_id, {
                "content": [{"type": "text", "text": f"未知工具: {tool_name}"}],
                "isError": True,
            })

        # 工具层错误也走 200 + isError（MCP 语义：协议层才用 JSON-RPC error）
        return _rpc_ok(req_id, {
            "content": [{"type": "text",
                         "text": json.dumps(result, ensure_ascii=False, default=str)}],
            "isError": bool(isinstance(result, dict) and "error" in result),
        })

    return _rpc_err(req_id, -32601, f"未知方法: {method}（支持 initialize | ping | tools/list | tools/call）")
