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
from yuanzhu.api.dialog import router as dialog_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    await _autoregister_builtin_templates()
    yield


async def _autoregister_builtin_templates():
    """v0.2 首启体验：自动注册包内内置模板（深度问答/AIQA/会议等）——pip 装完零配置可用"""
    from pathlib import Path as _P
    import yuanzhu
    builtin = _P(yuanzhu.__file__).parent / "templates"
    if not builtin.is_dir():
        return
    from yuanzhu.db.database import async_session_factory
    from yuanzhu.template.store import TemplateStore
    from yuanzhu.db.models import Template
    from sqlalchemy import select
    async with async_session_factory() as session:
        store = TemplateStore(session)
        existing = {t.name for t in (await session.execute(select(Template))).scalars().all()}
        registered = []
        for tpl_dir in sorted(builtin.iterdir()):
            if tpl_dir.is_dir() and (tpl_dir / "manifest.yaml").is_file():
                if tpl_dir.name not in existing:
                    await store.register_dir(tpl_dir)
                    registered.append(tpl_dir.name)
        await session.commit()
        if registered:
            print(f"  内置模板已注册: {', '.join(registered)}")


app = FastAPI(
    title="元铸工坊",
    description="企业 AI 人效平台——本体层 + MCP + 模板库",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(mcp_router)


# ---------- Bearer 认证（审查 I5；未配 token=零摩擦本机模式） ----------
_auth_singleton = None

from fastapi import Request as _Request
from fastapi.responses import JSONResponse as _JSONResponse


@app.middleware("http")
async def bearer_auth(request: _Request, call_next):
    from yuanzhu.config import settings as _s
    global _auth_singleton
    if _auth_singleton is None:
        _auth_singleton = bool(_s.api_token)
    if not _auth_singleton:
        return await call_next(request)

    path = request.url.path
    exempt = (
        path == "/health"
        or path.startswith("/assets/")
        or (path in ("", "/") or (not path.startswith("/api") and not path.startswith("/v1")
                                  and not path.startswith("/mcp") and "." not in path.rsplit("/", 1)[-1]))
    )
    if exempt:
        return await call_next(request)

    auth = request.headers.get("Authorization", "")
    if auth == f"Bearer {_s.api_token}":
        return await call_next(request)
    return _JSONResponse(
        status_code=401,
        content={"detail": "未授权：需要 Authorization: Bearer <token>（服务端已启用认证）"},
    )

app.include_router(objects_router)
app.include_router(actions_router)
app.include_router(staged_router)
app.include_router(core_router)
app.include_router(gateway_router)
app.include_router(dialog_router)


@app.get("/health")
async def health():
    from yuanzhu import __version__
    return {"status": "ok", "mode": settings.mode, "version": __version__}


# ---------- Web 控制台静态托管（ADR-002；构建产物 server/static） ----------
from pathlib import Path as _Path
from fastapi.staticfiles import StaticFiles as _StaticFiles
from fastapi.responses import FileResponse as _FileResponse

_STATIC_DIR = _Path(__file__).resolve().parent / "static"   # v0.2：包内资源（PyPI 分发）
if _STATIC_DIR.is_dir():
    app.mount("/assets", _StaticFiles(directory=str(_STATIC_DIR / "assets")), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str):
        """SPA 兜底：静态文件直出，其余路径回 index.html（API 路由已先行注册，优先匹配）

        C2 修复：resolve + is_relative_to 防路径穿越（%2e%2e 编码绕过客户端规范化）。
        """
        if full_path:
            file = (_STATIC_DIR / full_path).resolve()
            if file.is_file() and file.is_relative_to(_STATIC_DIR.resolve()):
                return _FileResponse(file)
        return _FileResponse(_STATIC_DIR / "index.html")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("yuanzhu.main:app", host="127.0.0.1", port=8600, reload=settings.debug)
