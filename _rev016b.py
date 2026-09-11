# -*- coding: utf-8 -*-
"""v0.1.6 核心修订：推衍引擎从附加层提升为核心骨架"""
from pathlib import Path

p = Path("docs/superpowers/plans/2026-09-11-v0.1.6-inference.md")
src = p.read_text(encoding="utf-8")

# 重写 Goal 和 Architecture
old = """**Goal**: 从被动响应转向主动推衍——基于三记忆系统交叉分析，推衍用户意图，交付超预期结果

**Architecture**: Letta 心跳模式 + Mem0 自动提取 + 三记忆系统理论
- **Episodic**（新增）：BehaviorLog 记录用户行为序列
- **Semantic**（已有）：Insight 知识库
- **Procedural**（已有）：Workflow/Template
- **心跳引擎**（新增）：定期交叉分析三系统 → 产出 Proposition（主动提议+交付物草稿）"""
new = """**Goal**: 推衍引擎作为核心骨架（不是附加层）——系统持续观察→推衍→准备→呈现，用户来时已有惊喜等着

**核心转变**（用户洞察 2026-09-11）：
```
旧架构：用户问 → 触发流水线 → 跑完 → 附加建议（主动是皮）
新架构：推衍引擎持续运行 → 主动准备好 → 用户来时呈现（主动是骨架）
```

**Architecture**: 事件驱动推衍引擎（Letta 心跳理论 + 事件触发）
- **观察层**（Episodic）：BehaviorLog——每个用户操作自动触发推衍引擎
- **知识层**（Semantic）：Insight——推衍引擎持续在知识库上做交叉分析
- **技能层**（Procedural）：Workflow/Template——推衍引擎主动准备交付物
- **推衍引擎**（核心）：**事件驱动**（不等定时）——每次行为后自动分析
  ```
  自主循环：观察→推衍→准备→呈现→学习→再观察
  ```
- **呈现通道**：Chat 对话内 + 通知中心（两条路）"""
assert src.count(old) == 1
src = src.replace(old, new)

# T3 修订：从"心跳"改为"事件驱动"
old = """### T3 心跳推衍引擎

**Files:**
- Create: `server/src/yuanzhu/inference/engine.py`
- Create: `server/src/yuanzhu/inference/models.py`（Proposition ORM）
- Modify: `server/src/yuanzhu/api/core.py`（POST /inference/run）
- Test: `server/tests/test_t3_heartbeat.py`

**Interfaces:**
- Consumes: BehaviorLog（近 7 天）+ Insight（全部）+ Template（全部）+ BehaviorLog（采纳/忽略历史）
- Produces: `Proposition` ORM（id/type/insight/advice/deliverable_draft_json/status/confidence）
- Produces: `POST /inference/run` → List[Proposition]"""
new = """### T3 事件驱动推衍引擎（核心——不是后台 job）

**Files:**
- Create: `server/src/yuanzhu/inference/engine.py`
- Create: `server/src/yuanzhu/inference/models.py`（Proposition ORM）
- Create: `server/src/yuanzhu/inference/__init__.py`
- Modify: `server/src/yuanzhu/api/core.py`（POST /inference/run + 行为端点后自动触发）
- Test: `server/tests/test_t3_inference_engine.py`

**Interfaces:**
- Consumes: BehaviorLog（近 N 条）+ Insight（全部）+ Template（摘要）+ Proposition 历史（偏好）
- Produces: `Proposition` ORM（id/type/insight/advice/deliverable_draft_json/status/confidence）
- Produces: `POST /inference/run` → List[Proposition]（手动触发）
- Produces: **自动触发**——每个关键行为端点完成后异步调用推衍引擎

**事件驱动设计**（主动是骨架，不是定时 job）：
```python
# 不等定时——每个行为都是推衍引擎的输入信号
async def _trigger_inference(session, event_type, event_detail):
    \"\"\"行为后自动触发推衍引擎（异步，不阻塞用户操作）\"\"\"
    asyncio.ensure_future(_run_inference_async(event_type, event_detail))

# 埋入点（在 T1 的 _log_behavior 里统一触发）：
#   ask → 推衍引擎分析"用户在问什么方向的问题"
#   adopt → 推衍引擎分析"用户觉得什么有价值"
#   forge → 推衍引擎分析"用户在创造什么工具"
#   approve/reject → 推衍引擎分析"用户接受什么拒绝什么"
```

**推衍引擎自主循环**：
```
观察（新事件到了）→ 推衍（交叉分析三记忆系统）→ 准备（生成 Proposition + 交付物草稿）
→ 呈现（Chat 推送 or 通知中心等待）→ 学习（用户 accept/dismiss 反馈）→ 再观察
```"""
assert src.count(old) == 1
src = src.replace(old, new)

# 顺序修订
old = """T1（Episodic 基础）→ T1.5（behavior_step）→ T2（对话内推衍，依赖 T1+T1.5）
                   → T3（后台心跳，依赖 T1+已有 Semantic/Procedural）
                   → T4（通知中心，依赖 T3 的 Proposition）
                   → T5（偏好闭环，依赖 T4 的 accept/dismiss 信号）
                   → T6（效果评估，依赖 T4 的数据积累）"""
new = """T1（Episodic 基础 + 行为埋点含事件触发钩子）
→ T1.5（behavior_step 步骤类型）
→ T3（推衍引擎核心——事件驱动，不等 T2）
→ T2（deep-answer infer 步骤——推衍引擎在对话中的呈现接口）
→ T4（通知中心——推衍引擎的第二个呈现通道）
→ T5（偏好学习——推衍引擎的自我调节）
→ T6（效果评估——推衍引擎的质量度量）"""
assert src.count(old) == 1
src = src.replace(old, new)

# 追加架构修订记录
src += """

## 架构修订记录（2026-09-11 用户洞察）

**用户洞察**：开发元铸工坊的工作本身就是元铸工坊的活——"AI 提议人审"只是治理底线，产品的本质是**主动**（推衍/创造/挖掘/学习）。推衍引擎不是附加功能，是核心骨架。

**具体调整**：
1. T3 从"定时心跳"改为"事件驱动"——每个用户行为自动触发推衍引擎（不等定时）
2. T2 infer 步骤定位为"推衍引擎在对话中的呈现接口"（不是独立功能）
3. 推衍引擎有自主循环：观察→推衍→准备→呈现→学习→再观察
4. T1 的行为埋点统一包含事件触发钩子（不只是记录，还是推衍引擎的输入信号）
"""
p.write_text(src, encoding="utf-8")
print("v0.1.6 核心修订完成：推衍引擎从附加层→核心骨架")
