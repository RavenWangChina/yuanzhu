# server —— 中控服务（模块化单体）

元铸工坊中控：本体层 + staged writes 状态机 + MCP + 模板库 + 任务编排 + 模型网关 + Web 托管。

## 运行

```bash
python -m venv .venv
.venv/Scripts/pip install -e ".[dev]"
.venv/Scripts/python -m pytest tests/          # 104 个测试
.venv/Scripts/python -m uvicorn yuanzhu.main:app --port 8600
```

- Web 控制台：http://127.0.0.1:8600 （静态产物由 web/ 构建，已随仓）
- MCP 端点：`POST /mcp`（tools/list | tools/call）
- 模型接入**零配置**：自动导入 dsh 已配 provider（ADR-014，OpenAI 兼容协议全家桶）；自定义端点用 `YUANZHU_PROVIDER_n_*` 环境变量
- 企微配置（挂起中）见 [docs/对话学习企微接入指南.md](../docs/对话学习企微接入指南.md)
- H2 测试种子：`python seed_h2.py`

## 结构

- `src/yuanzhu/db/` 模型与连接；`ontology/` 对象/链接/动作存储与 DSL 解析
- `staged/` 状态机+criteria 校验+transform 引擎+执行器/补偿器
- `mcp/` 工具生成与请求分发；`api/` REST 端点；`template/` 四段式注册
- `workflow/` 执行引擎；`evals/` 评测执行器；`dialog/` 对话学习（缓冲+提炼）
- `gateway/` LiteLLM 网关与计量；`node/` `task/` 编排
