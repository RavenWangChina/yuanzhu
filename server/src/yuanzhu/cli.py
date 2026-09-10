"""yuanzhu CLI —— 开发者第一界面，中控 API 的薄壳（ADR-012）

命令集（v0.1）：status / query / pending / approve / reject /
             templates / run / mcp tools

实现约束：标准库 argparse（零新依赖）；HTTP 用 httpx（已在依赖）。
测试通过 make_client() 注入 ASGITransport client（不起真端口）。
"""
import argparse
import asyncio
import contextlib
import json
import sys
from typing import Optional

import httpx

from yuanzhu.config import settings


@contextlib.asynccontextmanager
async def make_client():
    """默认连本机中控（YUANZHU_BASE_URL 可覆盖；配了 api_token 自动携带）"""
    headers = {"Authorization": f"Bearer {settings.api_token}"} if settings.api_token else {}
    async with httpx.AsyncClient(base_url=settings.base_url, timeout=120, headers=headers) as client:  # forge 类长操作
        yield client


class Ctx:
    """输出与退出码的载体（测试注入用）"""

    def __init__(self):
        self.exit_code = 0
        self._lines = []

    def print(self, *args):
        line = " ".join(str(a) for a in args)
        self._lines.append(line)
        print(line)  # 真实终端输出

    @property
    def output(self):
        return "\n".join(self._lines)


async def _get(client, path, ctx: Ctx, ok_codes=(200,)):
    resp = await client.get(path)
    if resp.status_code not in ok_codes:
        detail = _detail(resp)
        ctx.print(f"✗ HTTP {resp.status_code}: {detail}")
        ctx.exit_code = 1
    return resp


async def _post(client, path, body, ctx: Ctx):
    resp = await client.post(path, json=body)
    if resp.status_code >= 400:
        ctx.print(f"✗ HTTP {resp.status_code}: {_detail(resp)}")
        ctx.exit_code = 1
    return resp


def _detail(resp) -> str:
    try:
        return resp.json().get("detail", resp.text[:200])
    except Exception:
        return resp.text[:200]


def _parse_filter(pairs: list) -> dict:
    out = {}
    for p in pairs or []:
        k, _, v = p.partition("=")
        if not k:
            raise SystemExit(f"过滤条件格式应为 k=v：{p}")
        out[k] = v
    return out


# ---------- 子命令实现 ----------

async def cmd_status(client, args, ctx):
    resp = await _get(client, "/health", ctx)
    if ctx.exit_code == 0:
        d = resp.json()
        ctx.print(f"✓ {d['status']} | mode={d['mode']} | v{d.get('version', '?')}")


async def cmd_query(client, args, ctx):
    resp = await _post(client, "/mcp", {
        "method": "tools/call",
        "params": {"name": f"query_{args.domain}_{args.type}".lower(),
                   "arguments": {"filter": _parse_filter(args.filter), "limit": args.limit}},
    }, ctx)
    if ctx.exit_code:
        return
    objects = resp.json().get("objects", [])
    if not objects:
        ctx.print("（无匹配对象）")
        return
    for o in objects:
        title = o.get("title") or "?"
        ctx.print(f"#{o['id']}  {title}")
        if args.verbose:
            ctx.print(f"      {json.dumps(o.get('properties', {}), ensure_ascii=False)}")


async def cmd_pending(client, args, ctx):
    resp = await _get(client, "/api/staged/pending", ctx)
    if ctx.exit_code:
        return
    items = resp.json()
    if not items:
        ctx.print("🎉 没有待审事项")
        return
    for it in items:
        before = it.get("before") or {}
        ctx.print(f"#{it['id']}  {it['action']}  by={it['staged_by']}")
        ctx.print(f"      params: {json.dumps(it['params'], ensure_ascii=False)}")
        if before:
            ctx.print(f"      before: {json.dumps(before, ensure_ascii=False)}")


async def cmd_approve(client, args, ctx):
    resp = await _post(client, f"/api/staged/{args.exec_id}/approve", {
        "reviewed_by": args.reviewer, "review_comment": args.comment or "CLI 批准",
    }, ctx)
    if ctx.exit_code == 0:
        ctx.print(f"✓ #{args.exec_id} {resp.json()['status']}")


async def cmd_reject(client, args, ctx):
    if not args.comment:
        ctx.print("✗ 拒绝必须附理由：--comment \"原因\"")
        ctx.exit_code = 1
        return
    resp = await _post(client, f"/api/staged/{args.exec_id}/reject", {
        "reviewed_by": args.reviewer, "review_comment": args.comment,
    }, ctx)
    if ctx.exit_code == 0:
        ctx.print(f"✓ #{args.exec_id} {resp.json()['status']}")


async def cmd_templates(client, args, ctx):
    resp = await _get(client, "/api/templates", ctx)
    if ctx.exit_code:
        return
    for t in resp.json():
        ctx.print(f"{t['name']} v{t['version']} [{t['status']}] {t['domain']}")
        for w in t.get("workflows_json") or []:
            ctx.print(f"  · {w['name']} — {w.get('description', '')}")
        if t["status"] == "draft":
            layer = (t.get("manifest_json") or {}).get("layer")
            if layer:
                ctx.print(f"  （对话学习候选 · {layer}）")


async def cmd_run(client, args, ctx):
    params = _parse_filter(args.param)
    resp = await _post(client, "/api/workflows/run", {
        "domain": args.domain, "workflow": args.workflow,
        "params": params, "run_by": "cli",
    }, ctx)
    if ctx.exit_code:
        return
    result = resp.json()
    staged = 0
    for sid, s in (result.get("steps") or {}).items():
        if isinstance(s, dict):
            if s.get("status") == "staged":
                staged += 1
            staged += s.get("staged_count", 0)
    ctx.print(f"✓ {result['workflow']} 运行完成（{staged} 项产出待审）")
    if staged:
        ctx.print("  → yuanzhu pending 查看 / yuanzhu approve <id> 审批")


async def cmd_forge(client, args, ctx):
    resp = await _post(client, "/api/templates/forge",
                       {"description": args.description}, ctx)
    if ctx.exit_code:
        return
    d = resp.json()
    badge = "✅ 已上架" if d["status"] == "published" else "⚠ evals 未全过，留在草稿区"
    ctx.print(f"{badge}: {d['name']}")
    ctx.print(f"  evals: {d['evals']['passed']}/{d['evals']['total']} 通过"
              + (f"，失败: {', '.join(d['evals']['failures'])}" if d['evals']['failures'] else ""))
    ctx.print(f"  目录: {d['directory']}（可人工微调后重新注册）")
    if d["status"] == "published":
        ctx.print("  → 模板市场立即可用；yuanzhu mcp tools 查看 agent 新能力")


async def cmd_import(client, args, ctx):
    from pathlib import Path as _P
    path = _P(args.file)
    if not path.is_file():
        ctx.print(f"✗ 文件不存在: {args.file}")
        ctx.exit_code = 1
        return
    text = path.read_text(encoding="utf-8", errors="replace")
    resp = await _post(client, "/api/dialog/import", {
        "text": text, "group_name": args.group,
    }, ctx)
    if ctx.exit_code:
        return
    d = resp.json()
    ctx.print(f"✓ 导入 {d['imported']} 条（噪音跳过 {d['skipped_noise']}）")
    if args.refine:
        r2 = await _post(client, "/api/dialog/refine", {"min_messages": 3}, ctx)
        if ctx.exit_code == 0 and r2.json()["candidates"]:
            ctx.print(f"✓ 提炼出 {r2.json()['candidates']} 个候选 → 模板市场草稿区")
        else:
            ctx.print("（未提炼出候选——样本可能不足或无高频模式）")


async def cmd_mcp_tools(client, args, ctx):
    resp = await _post(client, "/mcp", {"method": "tools/list", "params": {}}, ctx)
    if ctx.exit_code:
        return
    for t in resp.json().get("tools", []):
        ctx.print(f"{t['name']}  — {t.get('description', '')[:60]}")


# ---------- 装配 ----------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="yuanzhu", description="元铸工坊 CLI（API 薄壳）")
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("status", help="中控健康检查")

    q = sub.add_parser("query", help="查询本体对象（经 MCP）")
    q.add_argument("domain")
    q.add_argument("type")
    q.add_argument("--filter", nargs="*", default=[], metavar="k=v", help="属性过滤")
    q.add_argument("--limit", type=int, default=20)
    q.add_argument("-v", "--verbose", action="store_true", help="显示完整属性")

    sub.add_parser("pending", help="列出待审动作")

    a = sub.add_parser("approve", help="批准待审动作")
    a.add_argument("exec_id", type=int)
    a.add_argument("--comment")
    a.add_argument("--reviewer", default="cli-reviewer")

    r = sub.add_parser("reject", help="拒绝待审动作（必须附理由）")
    r.add_argument("exec_id", type=int)
    r.add_argument("--comment", required=False)
    r.add_argument("--reviewer", default="cli-reviewer")

    sub.add_parser("templates", help="列出已装模板与工作流")

    run = sub.add_parser("run", help="触发工作流")
    run.add_argument("domain")
    run.add_argument("workflow")
    run.add_argument("--param", nargs="*", default=[], metavar="k=v", help="工作流参数")

    fg = sub.add_parser("forge", help="一句话铸模板（AI 生成四段式，evals 守门）")
    fg.add_argument("description", help="描述你的工作场景，如：我每天要收集各组周报汇总成一份")

    imp = sub.add_parser("import", help="导入聊天记录文件（企微/微信导出 txt）")
    imp.add_argument("file", help="聊天记录文本文件路径")
    imp.add_argument("--group", default="导入会话", help="群/会话名")
    imp.add_argument("--refine", action="store_true", help="导入后立即提炼")

    mcp = sub.add_parser("mcp", help="MCP 工具")
    mcp_sub = mcp.add_subparsers(dest="mcp_cmd", required=True)
    mcp_sub.add_parser("tools", help="列出 MCP 工具")

    return p


HANDLERS = {
    "status": cmd_status, "query": cmd_query, "pending": cmd_pending,
    "approve": cmd_approve, "reject": cmd_reject, "templates": cmd_templates,
    "run": cmd_run, "mcp": cmd_mcp_tools, "import": cmd_import, "forge": cmd_forge,
}


async def _amain(args, ctx: Ctx) -> int:
    try:
        async with make_client() as client:
            await HANDLERS[args.command](client, args, ctx)
    except httpx.ConnectError as e:
        ctx.print(f"✗ 连不上中控（{settings.base_url}）：{e}")
        ctx.print("  先启动：python -m uvicorn yuanzhu.main:app --port 8600")
        ctx.exit_code = 1
    return ctx.exit_code


def main(argv: Optional[list] = None, _ctx: Optional[Ctx] = None) -> int:
    """入口（pyproject [project.scripts]）"""
    args = build_parser().parse_args(argv)
    return asyncio.run(_amain(args, _ctx or Ctx()))


if __name__ == "__main__":
    sys.exit(main())
