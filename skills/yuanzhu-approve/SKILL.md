---
name: yuanzhu-approve
description: 查看并审批元铸工坊的待审操作（AI 的 staged writes 待人拍板）。当用户说"看看待审/有什么要审批的/批准一下"，或刚触发过 execute_ 类写操作时使用。
---

# 待审审批（Staged Writes）

元铸工坊里 AI 的写操作先暂存等人审——这个技能帮你把待办念清楚，等人拍板。

## 前置检查

MCP 工具调不通时提示用户：`pip install yuanzhu` 后运行 `yuanzhu-server`。

## 步骤

1. **拉待审清单**：调 MCP 工具 `list_pending_approvals`。
2. **逐条人话解读**（这是本技能的核心价值——原始 JSON 对用户不友好）：
   - 什么动作（如 CreateTask）
   - 动了什么对象、关键字段值（标题/内容摘要）
   - 谁提交的、什么时候
   - 例：「第 3 条：AI 想创建任务"完成 Q3 财报核对"，状态字段=进行中——批准吗？」
3. **等用户明确表态**再动作：
   - 批准 → `approve_action {"exec_id": N}`
   - 拒绝 → `reject_action {"exec_id": N}`，可带拒绝理由
   - **禁止**替用户默认批准——staged writes 的意义就是人拍板。
4. 批完汇报结果（成功/失败+原因）。

## 边界

- 一次多批：用户说"全部批准"才连发多个 approve_action；有歧义（如"除了第一条"）先复述清单确认。
- revert 不在本技能范围（需要时引导去 Web 待审中心）。
