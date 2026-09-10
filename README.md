# 元铸工坊 SOSOFAST

> 对外传播名 **SOSOFAST（元铸工坊）** · 技术生态名 **yuanzhu** · © MiaoYu

**按企业自身的工作习惯，把各领域的最佳实践定向复刻成 AI 工作流资产——像软件一样被开发、分发、使用、沉淀、进化，全员开箱即用。**

## 当前状态：v0.1 已交付（技术验证期）

八里程碑全部完成（2026-09-10，104 测试全绿）：本体层（对象/链接/动作+staged writes 状态机）、MCP 暴露、中控骨架（节点/任务/模板/LiteLLM 网关）、Web 控制台 4 页、AIQA 四段式首发模板、工作流执行引擎、对话学习采集服务端、H2 真人测试场景包。

三柱验证：**H7 轻量本体已全通**；H1 专家线全通（对话线服务端就绪，待真实企微数据）；H2 链路就绪（待真人测试）。

### 快速开始（单机模式）

```bash
# 中控服务（含 Web 控制台，Python 3.11+）
cd server
python -m venv .venv && .venv/Scripts/pip install -e ".[dev]"
.venv/Scripts/python -m uvicorn yuanzhu.main:app --port 8600
# 打开 http://127.0.0.1:8600 （待审中心/模板市场/节点拓扑/用量审计）

# CLI（开发者第一界面）
yuanzhu status && yuanzhu pending && yuanzhu templates

# 跑测试
.venv/Scripts/python -m pytest tests/

# 注册首发模板 + 造 H2 测试数据
.venv/Scripts/python seed_h2.py
```

Web 控制台前端源码在 `web/`（Vite+Vue3，构建产物由 FastAPI 托管）；模型接入零配置：网关自动导入 dsh 已配的 provider（天翼云等，OpenAI 兼容协议全家桶）；自定义端点用 `YUANZHU_PROVIDER_n_*` 环境变量。

## 文档导航

| 文档 | 内容 |
|------|------|
| **[docs/使用场景与接入形态.md](docs/使用场景与接入形态.md)** | **入门首选：三种用户怎么用 + Claude Code 接入** |
| [docs/specs/v0.1-design.md](docs/specs/v0.1-design.md) | v0.1 设计文档（已实现） |
| [docs/架构决策记录.md](docs/架构决策记录.md) | ADR-001~014：全部已确认架构决策 |
| [docs/技术验证路线.md](docs/技术验证路线.md) | 六假设验证路线（H1-H7）与出口条件 |
| [docs/元流程-v2.md](docs/元流程-v2.md) | 六环节×知识环完整规格（工坊内核） |
| [docs/Palantir范式学习报告.md](docs/Palantir范式学习报告.md) | 知识层轻量本体的设计依据 |
| [docs/对话学习企微接入指南.md](docs/对话学习企微接入指南.md) | 企微回调配置（管理员自助） |
| [docs/test-reports/H2真人测试场景包.md](docs/test-reports/H2真人测试场景包.md) | H2 真人测试的组织手册 |
| [docs/项目介绍书.pdf](docs/项目介绍书.pdf) | 项目介绍书（商业存档版） |
| [CHANGELOG.md](CHANGELOG.md) | 更新日志 |
| [ROADMAP.md](ROADMAP.md) | 版本计划 |
| [docs/致谢与引用出处.md](docs/致谢与引用出处.md) | 引用来源与致谢（特别感谢周志明先生） |

## 核心理念

- **工作流即软件（Workflow-as-Software）**：工作流走完整软件工程生命周期（需求对抗→方案审查→TDD→双通道审查→实证发布），不是画布上拖出来的
- **双输入工坊**：专家显性开发 + 从企业 IM 对话中学习（企业适配层自动生成）
- **轻量本体**：知识层为「对象+关系+动作」三件套，staged writes 人审分级（读高写低），MCP 原生暴露
- **执行底座无关**：方法论资产不绑定任何 AI 执行框架
- **解放人力，不是替代人力**

## License

**AGPL-3.0**（强保护协议：防闭源白嫖，为企业版保留商业授权空间——ADR-009 决策）。

## 致谢

本项目引用了周志明（icyfenix）先生《设计机器学习应用系统》等外部来源，完整清单见 [docs/致谢与引用出处.md](docs/致谢与引用出处.md)。
