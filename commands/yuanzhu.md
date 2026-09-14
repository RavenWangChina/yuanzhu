---
description: 元铸工坊总览——待审数量、已铸模板、最近行为
---

# 元铸工坊总览

用元铸工坊的 MCP 工具完成（服务未启动则提示 `pip install yuanzhu && yuanzhu-server`）：

1. `list_pending_approvals` → 待审数量；有就逐条人话解读（动作/对象/关键字段），问用户要不要批
2. 查已铸模板（query_ 系列工具查 Template 对象，或 GET http://127.0.0.1:8600/api/templates）→ 列出名称+状态+一句话描述
3. 汇总输出：

```
## 元铸工坊
- 待审：N 条（最多列 5 条摘要）
- 模板：M 个（published X / draft Y）
- 下一步建议：有待审→先审；无待审且用户描述过重复工作→建议 forge 铸模板
```

不要主动执行任何写操作。
