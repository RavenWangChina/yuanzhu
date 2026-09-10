"""MCP Streamable HTTP 端点（JSON-RPC 风格子集：tools/list + tools/call）"""
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from yuanzhu.db.database import get_db
from yuanzhu.mcp.tools import MCPToolGenerator
from yuanzhu.mcp.handlers import MCPHandlers

router = APIRouter(tags=["mcp"])


@router.post("/mcp")
async def handle_mcp(request: Request, db: AsyncSession = Depends(get_db)):
    body = await request.json()
    method = body.get("method")
    params = body.get("params", {})
    agent_id = request.headers.get("X-Agent-ID", "unknown-agent")

    if method == "tools/list":
        tools = await MCPToolGenerator(db).list_tools()
        return JSONResponse({"tools": tools})

    if method == "tools/call":
        tool_name = params.get("name", "")
        arguments = params.get("arguments", {})
        handlers = MCPHandlers(db)

        if tool_name.startswith("query_"):
            result = await handlers.handle_query(tool_name, arguments)
        elif tool_name.startswith("execute_"):
            result = await handlers.handle_execute(tool_name, arguments, agent_id)
        elif tool_name == "list_pending_approvals":
            result = await handlers.handle_list_pending(arguments)
        elif tool_name == "approve_action":
            result = await handlers.handle_approve(arguments, agent_id)
        elif tool_name == "reject_action":
            result = await handlers.handle_reject(arguments, agent_id)
        else:
            result = {"error": f"未知工具: {tool_name}"}

        status = 200 if "error" not in result else 200  # MCP 语义错误也走 200（工具层错误）
        return JSONResponse(result, status_code=status)

    return JSONResponse({"error": f"未知方法: {method}（v0.1 支持 tools/list | tools/call）"}, status_code=400)
