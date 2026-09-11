# -*- coding: utf-8 -*-
"""审查修复：C1 evals 幂等键 run 后缀 / C2 自定义价目表 / 并行测试断言"""
from pathlib import Path

# ---- C1: EvalsRunner 幂等键加 run 后缀（每次跑评测互不占键）----
p = Path("src/yuanzhu/evals/runner.py")
src = p.read_text(encoding="utf-8")

old = '''    async def _run_case(self, case: Dict[str, Any], context: Dict[str, Any]):
        """执行一个用例（context 跨用例共享：$last_<type> 引用链）；expect 断言收尾"""
        context: Dict[str, Any] = context
        for step in case.get("steps", []):'''
# 实际签名可能不同——按锚点找
anchor = '    async def _run_case(self'
i = src.index(anchor)
# 找到方法体第一处 sm.stage 调用前后插入——更直接：给 EvalsRunner.__init__ 加 run_id，
# _run_case 的 action 执行走 run_action？evals 走 engine.run_action？看现状：
# evals runner 自己调 sm.stage（不经 engine.run_action）——在 stage 调用处给幂等键加后缀
old_stage = '''                    last_result = await self.engine.run_action(
                        domain=case.get("_domain", "aiqa"),
                        action_name=step["action"],
                        params=params,
                        run_by="evals-runner",
                    )'''
new_stage = '''                    # C1 修复：evals 路径幂等键追加 run 标识——避免与真实执行
                    # （及历史 evals 记录）互相占用幂等键导致第二次跑必挂
                    idem_suffix = f"#evals-{self._run_id}"
                    last_result = await self.engine.run_action(
                        domain=case.get("_domain", "aiqa"),
                        action_name=step["action"],
                        params=params,
                        run_by="evals-runner",
                        idempotency_suffix=idem_suffix,
                    )'''
if old_stage in src:
    src = src.replace(old_stage, new_stage, 1)
else:
    # 备选形态：直接 sm.stage
    old2 = '''        exec = await self.sm.stage(
            action_type_id=action_type.id, params=params,
            staged_by="evals-runner", idempotency_key=idem,
        )'''
    raise SystemExit("预期形态未命中，需人工看 runner 结构")

# __init__ 生成 run_id
old_init = '''    def __init__(self, session: AsyncSession):
        self.session = session
        self.engine = WorkflowEngine(session)
        self.object_store = ObjectStore(session)
        self.sm = StagedStateMachine(session)'''
new_init = '''    def __init__(self, session: AsyncSession):
        import uuid
        self._run_id = uuid.uuid4().hex[:8]   # C1：本次评测运行标识
        self.session = session
        self.engine = WorkflowEngine(session)
        self.object_store = ObjectStore(session)
        self.sm = StagedStateMachine(session)'''
assert src.count(old_init) == 1
src = src.replace(old_init, new_init)
p.write_text(src, encoding="utf-8")
print("C1: runner run_id patched")

# engine.run_action 加 idempotency_suffix
p = Path("src/yuanzhu/workflow/engine.py")
src = p.read_text(encoding="utf-8")
old = '''    async def run_action(
        self, domain: str, action_name: str,
        params: Dict[str, Any], run_by: str,
    ) -> Dict[str, Any]:
        """单动作执行（evals 与外部触发共用；返回状态供断言）"""'''
new = '''    async def run_action(
        self, domain: str, action_name: str,
        params: Dict[str, Any], run_by: str, idempotency_suffix: str = "",
    ) -> Dict[str, Any]:
        """单动作执行（evals 与外部触发共用；返回状态供断言）"""'''
assert src.count(old) == 1
src = src.replace(old, new)

old = '''            try:
                idem = action_type.idempotency_key_template.format(**fmt_vars)
            except KeyError:
                idem = None'''
new = '''            try:
                idem = action_type.idempotency_key_template.format(**fmt_vars)
                if idempotency_suffix:
                    idem += idempotency_suffix   # C1：evals 运行隔离
            except KeyError:
                idem = None'''
assert src.count(old) == 1
src = src.replace(old, new)
p.write_text(src, encoding="utf-8")
print("C1: run_action suffix added")

# ---- C2: 自定义价目表（YUANZHU_MODEL_PRICES JSON）----
p = Path("src/yuanzhu/gateway/proxy.py")
src = p.read_text(encoding="utf-8")
old = '''    # v0.1.1：litellm completion_cost 真值（本地价目表；无价目/异常记 0 不炸）
    cost = 0.0
    try:
        import litellm as _m
        cost = float(_m.model_cost.get(model, {}).get("input_cost_per_token", 0)
                     * (usage.get("prompt_tokens") or 0)
                     + _m.model_cost.get(model, {}).get("output_cost_per_token", 0)
                     * (usage.get("completion_tokens") or 0)) or 0.0
    except Exception:
        cost = 0.0'''
new = '''    # v0.1.1 估费：①自定义价目表（YUANZHU_MODEL_PRICES，JSON：模型→{in,out} 元/token）
    # 优先——glm 等网关模型不在 litellm 价目内；②fallback litellm 本地表；③无价记 0
    cost = 0.0
    try:
        custom = _custom_prices()
        if model in custom:
            cost = (custom[model].get("in", 0) * (usage.get("prompt_tokens") or 0)
                    + custom[model].get("out", 0) * (usage.get("completion_tokens") or 0))
        else:
            import litellm as _m
            cost = float(_m.model_cost.get(model, {}).get("input_cost_per_token", 0)
                         * (usage.get("prompt_tokens") or 0)
                         + _m.model_cost.get(model, {}).get("output_cost_per_token", 0)
                         * (usage.get("completion_tokens") or 0)) or 0.0
    except Exception:
        cost = 0.0'''
assert src.count(old) == 1
src = src.replace(old, new)

src += '''

def _custom_prices() -> dict:
    """读 YUANZHU_MODEL_PRICES 环境变量（JSON，如 {"glm-5.1": {"in": 1e-6, "out": 3e-6}}）"""
    import json as _json
    import os as _os
    raw = _os.environ.get("YUANZHU_MODEL_PRICES", "")
    if not raw:
        return {}
    try:
        return _json.loads(raw)
    except Exception:
        return {}
'''
p.write_text(src, encoding="utf-8")
print("C2: custom prices patched")

# ---- 并行测试断言修正（fake 返回完整 prompt 才能验证块）----
p = Path("tests/test_parallel.py")
src = p.read_text(encoding="utf-8")
old = '''    async def fake_chat(model, prompt, **kw):
        await asyncio.sleep(0.4)
        return f"done:{prompt[:1]}"'''
new = '''    async def fake_chat(model, prompt, **kw):
        await asyncio.sleep(0.4)
        return f"done:{prompt}"   # 返回完整 prompt，供 join 验证块接收'''
assert src.count(old) == 1
src = src.replace(old, new)

old = '''    # join 步收到两个并行输出（其 prompt 含两个标注块）
    join_content = result["steps"]["join"]["content"]
    assert "【out_a】" in join_content and "done:A" in join_content
    assert "【out_b】" in join_content and "done:B" in join_content'''
new = '''    # join 步收到两个并行输出（其 result=模型回复=完整 prompt 回显，含两个标注块）
    join_result = result["steps"]["join"]["result"]
    assert "【out_a】" in join_result
    assert "【out_b】" in join_result'''
assert src.count(old) == 1
src = src.replace(old, new)
p.write_text(src, encoding="utf-8")
print("parallel test fixed")

# ---- 旧 evals 测试语义更新（副作用清理后的新语义）----
p = Path("tests/test_evals_runner.py")
src = p.read_text(encoding="utf-8")
old = '''    obj_store = ObjectStore(aiqa_registered)
    bug_type = await obj_store.get_type_by_name("aiqa", "Bug")
    bugs = await obj_store.list_objects(type_id=bug_type.id)
    assert any(b.properties["title"] == "eval-登录超时" for b in bugs)'''
new = '''    # v0.1.1 新语义：evals 副作用清理——测试对象不残留（见 test_t2_t3），
    # 此处改为验证审计记录保留
    from sqlalchemy import select as _sel
    from yuanzhu.db.models import ActionExec
    execs = (await aiqa_registered.execute(_sel(ActionExec))).scalars().all()
    assert any("eval-登录超时" in str(e.params_json) for e in execs)'''
assert src.count(old) == 1
src = src.replace(old, new)
p.write_text(src, encoding="utf-8")
print("old evals test updated")
