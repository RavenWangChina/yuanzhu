"""MCP stdio 桥——把本地 yuanzhu-server 的 /mcp（Streamable HTTP）桥到 stdin/stdout。

MCP Registry 的 PyPI 包约定 stdio 传输：MCP 客户端把本模块当子进程启动，
每行一条 JSON-RPC（ndjson）。本桥纯透传到本地 HTTP 端点。

用法（前置：yuanzhu-server 已启动，默认 http://127.0.0.1:8600）：
    python -m yuanzhu.mcp_stdio
    # 或安装后的命令：yuanzhu-mcp
"""
import json
import os
import sys
import urllib.request

BASE = os.environ.get("YUANZHU_URL", "http://127.0.0.1:8600").rstrip("/") + "/mcp"
TOKEN = os.environ.get("YUANZHU_TOKEN", "")


def _post(payload: dict) -> dict | None:
    req = urllib.request.Request(
        BASE, data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", "Accept": "application/json"})
    if TOKEN:
        req.add_header("Authorization", f"Bearer {TOKEN}")
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode() or "{}")


def main() -> int:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue  # 噪声行静默丢弃
        try:
            resp = _post(payload)
            if resp is not None:
                sys.stdout.write(json.dumps(resp, ensure_ascii=False) + "\n")
                sys.stdout.flush()
        except Exception as e:  # 服务未启动等——作为 JSON-RPC 错误回给客户端
            req_id = payload.get("id")
            if req_id is not None:
                err = {"jsonrpc": "2.0", "id": req_id,
                       "error": {"code": -32603, "message": f"yuanzhu-server 不可达: {e}（请先运行 yuanzhu-server）"}}
                sys.stdout.write(json.dumps(err, ensure_ascii=False) + "\n")
                sys.stdout.flush()
            else:
                print(f"[yuanzhu-mcp] {e}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
