"""对话学习降级路径测试：聊天记录文本导入 → 提炼管线（spec 3.3 预案；企微挂起期的数据先行）"""
import pytest
from httpx import AsyncClient, ASGITransport

from yuanzhu.main import app
from yuanzhu.db.database import get_db
from yuanzhu.dialog.importer import parse_chat_text


# ---------- 解析器 ----------

def test_parse_wechat_export_format():
    """企微/微信导出的常见格式：时间 说话人\\n内容"""
    text = """2026-09-01 09:00:33 张三
昨日测试进展怎么样了？支付模块跑完了吗
2026-09-01 09:01:10 李四
还差退款场景，下午给你汇总
2026-09-01 09:05:00 张三
好，顺便把昨天那个回调重复扣款的 bug 也一起说下
"""
    msgs = parse_chat_text(text, chat_name="测试部")
    assert len(msgs) == 3
    assert msgs[0]["from"]["name"] == "张三"
    assert msgs[0]["text"]["content"] == "昨日测试进展怎么样了？支付模块跑完了吗"
    assert msgs[0]["chat"]["name"] == "测试部"
    assert msgs[1]["from"]["name"] == "李四"


def test_parse_skips_noise_lines():
    """非消息行（分隔线/系统提示）跳过并计数"""
    text = """————— 2026-09-01 —————
2026-09-01 09:00:33 张三
在吗
李四 撤回了一条消息
2026-09-01 09:01:00 李四
在
"""
    msgs, skipped = parse_chat_text(text, chat_name="g", return_skipped=True)
    assert len(msgs) == 2
    assert skipped >= 2  # 分隔线 + 撤回提示


# ---------- 导入端点 + 一条龙 ----------

async def test_import_and_refine_flow(db_session, monkeypatch):
    """导入端点 → buffer → 触发提炼 → 草稿区（一条龙，模型 mock）"""
    async def override():
        yield db_session
    app.dependency_overrides[get_db] = override

    # 模型 mock：提炼出 1 个候选
    import yuanzhu.dialog.refinement as ref_mod
    async def fake_llm(prompt, **kw):
        return '''[{"name": "日清汇总", "description": "张三每天要测试进展汇总",
          "trigger": "每日", "steps_draft": ["查当日 Bug", "AI 汇总"], "layer": "协同层"}]'''
    monkeypatch.setattr(ref_mod, "call_model", fake_llm)

    from yuanzhu.dialog.buffer import message_buffer
    message_buffer.clear()

    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://t") as c:
            text = "\n".join(
                [f"2026-09-0{i} 09:00:00 张三\n昨日测试进展怎么样了 {i}" for i in range(1, 6)]
            )
            resp = await c.post("/api/dialog/import", json={
                "text": text, "group_name": "测试部",
            })
            assert resp.status_code == 200
            data = resp.json()
            assert data["imported"] == 5
            assert len(message_buffer) >= 5

            # 立即提炼
            resp = await c.post("/api/dialog/refine", json={"min_messages": 3})
            assert resp.status_code == 200
            assert resp.json()["candidates"] == 1

            # 草稿区可见
            resp = await c.get("/api/templates?status=draft")
            assert any(t["name"] == "日清汇总" for t in resp.json())
    finally:
        app.dependency_overrides.clear()
        message_buffer.clear()


async def test_import_empty_rejected(db_session):
    async def override():
        yield db_session
    app.dependency_overrides[get_db] = override
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://t") as c:
            resp = await c.post("/api/dialog/import", json={"text": "", "group_name": "x"})
            assert resp.status_code == 400
    finally:
        app.dependency_overrides.clear()
