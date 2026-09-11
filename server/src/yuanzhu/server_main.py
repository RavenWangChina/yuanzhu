"""yuanzhu-server：一键启动入口（pip install yuanzhu 后敲这个命令）

用法：
    yuanzhu-server                # 默认 127.0.0.1:8600
    yuanzhu-server --port 9000
    yuanzhu-server --host 0.0.0.0 --port 8600   # 局域网可访问
"""
import argparse


def main():
    parser = argparse.ArgumentParser(
        prog="yuanzhu-server", description="元铸工坊中控服务（单机模式一键启动）")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8600)
    args = parser.parse_args()

    import uvicorn
    print(f"元铸工坊启动中… http://{args.host}:{args.port}")
    print("  首启自动注册内置模板（深度问答/AIQA 测试/会议追踪）")
    uvicorn.run("yuanzhu.main:app", host=args.host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
