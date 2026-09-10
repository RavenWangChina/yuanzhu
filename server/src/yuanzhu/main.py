"""元铸工坊中控服务入口（模块化单体：standalone | server | edge 由配置驱动）"""
from contextlib import asynccontextmanager

from fastapi import FastAPI

from yuanzhu.config import settings
from yuanzhu.db.database import init_db
from yuanzhu.mcp.server import router as mcp_router
from yuanzhu.api.objects import router as objects_router
from yuanzhu.api.actions import router as actions_router
from yuanzhu.api.staged import router as staged_router
from yuanzhu.api.core import router as core_router
from yuanzhu.gateway.router import router as gateway_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(
    title="元铸工坊",
    description="企业 AI 人效平台——本体层 + MCP + 模板库",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(mcp_router)
app.include_router(objects_router)
app.include_router(actions_router)
app.include_router(staged_router)
app.include_router(core_router)
app.include_router(gateway_router)


@app.get("/health")
async def health():
    return {"status": "ok", "mode": settings.mode, "version": "0.1.0"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("yuanzhu.main:app", host="127.0.0.1", port=8600, reload=settings.debug)
