# -*- coding: utf-8 -*-
"""H2 真人测试种子脚本：注册 AIQA 模板 + 造 Bug + 造一条待审（组织者跑）"""
import json
import sys
import urllib.request

BASE = "http://127.0.0.1:8600"


def post(path, body):
    req = urllib.request.Request(
        BASE + path,
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())


def get(path):
    with urllib.request.urlopen(BASE + path) as r:
        return json.loads(r.read())


def main():
    from pathlib import Path
    template_dir = Path(__file__).resolve().parent.parent / "templates" / "aiqa"

    # 1. 注册 AIQA 模板
    tpl = post("/api/templates/register", {"path": str(template_dir)})
    print(f"[1/4] 模板注册: {tpl['name']} {tpl['status']}")

    # 2. 造两个 Open Bug（报告任务的真实素材）
    types = get("/api/objects/types?domain=aiqa")
    bug_type = next(t for t in types if t["name"] == "Bug")
    for title, sev in [("支付回调偶发重复扣款", "critical"), ("退款入口 404", "major")]:
        post("/api/objects", {
            "type_id": bug_type["id"],
            "properties": {"title": title, "status": "Open", "severity": sev},
            "created_by": "seed",
        })
    print("[2/4] 种子 Bug: 2 条")

    # 3. 造一条待审（测试者的任务 1）：AI agent 提交一条新缺陷（staged 等审批）
    # 走 MCP 端点按名执行——与 H7 外部 agent 路径一致
    req = urllib.request.Request(
        BASE + "/mcp",
        data=json.dumps({
            "method": "tools/call",
            "params": {
                "name": "execute_aiqa_createbug",
                "arguments": {"title": "登录页在 IE 浏览器白屏", "severity": "major",
                              "module_name": "登录模块", "reproduce_steps": "IE11 打开登录页必现"},
            },
        }, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json", "X-Agent-ID": "qa-agent"},
        method="POST",
    )
    with urllib.request.urlopen(req) as r:
        result = json.loads(r.read())
    assert result.get("status") == "staged", result
    print("[3/4] 待审任务已造: AI 提交新缺陷「登录页在 IE 浏览器白屏」")

    # 4. 验证待审中心有内容
    pending = get("/api/staged/pending")
    print(f"[4/4] 待审中心: {len(pending)} 条")
    print("\n种子完成。测试者任务：")
    print("  1. 审批那条「登录页白屏」缺陷提交")
    print("  2. 模板市场用 test-report 生成报告（标题随意）")


if __name__ == "__main__":
    sys.exit(main())
