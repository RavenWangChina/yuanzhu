"""yuanzhu-demo：一键体验（v0.2.0「First 5 Minutes」）

启动服务 → 灌演示数据（demo 域 + 待审条目 + 一条洞见）→ 打开浏览器。
新用户 30 秒从安装到看见 staged writes 在工作。
"""
import argparse
import asyncio
import threading
import time
import webbrowser


def _wait_health(port: int, timeout: float = 30.0) -> bool:
    import urllib.request
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=2)
            return True
        except Exception:
            time.sleep(0.4)
    return False


async def _seed(port: int) -> dict:
    """灌演示数据：注册 demo 域 + AI 提交几条待审 + 一条已入库任务 + 一条洞见"""
    from yuanzhu.db.database import async_session_factory
    from yuanzhu.template.store import TemplateStore
    from yuanzhu.workflow.engine import WorkflowEngine
    from pathlib import Path

    tpl_dir = Path(__file__).parent / "templates" / "demo"
    stats = {"staged": 0, "objects": 0}
    async with async_session_factory() as session:
        await TemplateStore(session).register_dir(tpl_dir)
        engine = WorkflowEngine(session)

        # AI 提交三条待审（staged_by=assistant → 待审中心出现"AI 提交等人拍板"的条目）
        for title, pri in [("整理本周各小组进展并汇总成周报", 2),
                           ("把上周会议纪要里的行动项跟进一遍", 3),
                           ("给新同事准备环境配置清单", 1)]:
            try:
                await engine.run_action(
                    domain="demo", action_name="CreateDemoTask",
                    params={"title": title, "priority": pri},
                    run_by="demo-assistant")
                stats["staged"] += 1
            except Exception:
                pass  # 单条失败不阻塞演示

        # 一条已批准入库的任务（让对象列表非空 + CompleteDemoTask 有对象可玩）
        try:
            await engine.run_action(
                domain="demo", action_name="CreateDemoTask",
                params={"title": "体验：把这条任务标记完成（试试点批准）", "priority": 1},
                run_by="demo-assistant")
            from sqlalchemy import select as _sel
            from yuanzhu.db.models import ActionExec
            execs = (await session.execute(
                _sel(ActionExec).where(ActionExec.status == "staged")
                .order_by(ActionExec.id.desc()))).scalars().all()
            if execs:
                from yuanzhu.staged.state_machine import StagedStateMachine
                sm = StagedStateMachine(session)
                await sm.approve(execs[0].id, reviewed_by="demo-seeder")
                await sm.apply(execs[0].id)
                stats["objects"] += 1
        except Exception:
            pass

        # 一条洞见（知识库页非空）
        try:
            await engine.run_action(
                domain="metaflow", action_name="DistillInsight",
                params={"takeaway": "让 AI 干活前先说清「做什么、产出什么」，返工率显著下降",
                        "context": "demo 种子：来自周报汇总场景",
                        "source_question": "为什么要把工作铸成模板"},
                run_by="demo-seeder")
        except Exception:
            pass

        await session.commit()
    return stats


def main():
    parser = argparse.ArgumentParser(
        prog="yuanzhu-demo", description="元铸工坊一键体验（起服务+灌演示数据+开浏览器）")
    parser.add_argument("--port", type=int, default=8600)
    parser.add_argument("--no-browser", action="store_true", help="不自动打开浏览器")
    args = parser.parse_args()

    import uvicorn
    print("元铸工坊 Demo 启动中…")
    server = uvicorn.Server(uvicorn.Config(
        "yuanzhu.main:app", host="127.0.0.1", port=args.port, log_level="warning"))
    t = threading.Thread(target=server.run, daemon=True)
    t.start()

    if not _wait_health(args.port):
        print(f"✗ 服务未能在 {args.port} 端口就绪，退出")
        return 1

    stats = asyncio.run(_seed(args.port))
    url = f"http://127.0.0.1:{args.port}"
    print(f"✓ 服务就绪：{url}")
    print(f"✓ 演示数据已灌入：{stats['staged']} 条 AI 待审 · {stats['objects']} 条已入库任务 · 1 条洞见")
    print()
    print("三步体验（各 30 秒）：")
    print("  ① 待审中心 —— 看 AI 提交了什么，点「批准」让它入库（staged writes 核心体验）")
    print("  ② 对话页   —— 随便问一个工作问题，看答案如何沉淀")
    print("  ③ 模板市场 —— 在铸造框输入一句日常工作，看 AI 铸成模板")
    print()
    print("Ctrl+C 退出。")

    if not args.no_browser:
        webbrowser.open(f"{url}/staged")

    try:
        while t.is_alive():
            t.join(1)
    except KeyboardInterrupt:
        print("\n再见。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
