# 元铸工坊 SOSOFAST

> 对外传播名 **SOSOFAST（元铸工坊）** · 技术生态名 **yuanzhu** · © MiaoYu

**按企业自身的工作习惯，把各领域的最佳实践定向复刻成 AI 工作流资产——像软件一样被开发、分发、使用、沉淀、进化，全员开箱即用。**

## 当前状态：v0.1.5 已上架 [PyPI](https://pypi.org/project/yuanzhu/)（技术验证期）

**155 测试全绿**。装完即用的三层能力：

- **深度问答**（内置）：问一个问题自动走六步流水线——澄清 → 双视角**并行**作答 → 独立审查 → 综合裁决 → 人审采纳；采纳的洞见沉淀入库，后续提问自动反哺
- **一句话铸模板**（forge）：`yuanzhu forge "描述你的日常工作"` → AI 生成完整四段式模板 → **三道守门**（dry-run 结构校验 → evals 行为验证 → 人审）→ Web 重跑评测转正
- **对话长出工作流**：连续问同类问题，AI 发现模式后建议"铸成工作流？"——对话着对话着，工作流就长出来了
- **领域工作流**（内置 AIQA 测试/会议追踪）：staged writes——AI 的每个写操作进待审中心，人批准才生效；Claude Code 等经 MCP 直连本体

平台底座：本体层（对象+动作）、工作流引擎（并行组）、多协议模型网关（自动读 dsh 配置）、Web 控制台 + CLI、对话学习（聊天记录导入→AI 提炼工作流候选）。

三柱验证：**H7 轻量本体已全通**；H1 双线全通（专家线+对话线真实数据实证）；H2 模拟测试通过（真人测试待安排）。

### 快速开始（单机模式）

```bash
# 一键启动（Python 3.11+；pip 包含 Web 控制台与全部内置模板）
pip install yuanzhu
yuanzhu-server                 # 打开 http://127.0.0.1:8600
```

首启自动注册内置模板（深度问答/AIQA 测试/会议追踪）；CLI 同装：`yuanzhu status / pending / templates / forge`。

<details><summary>从源码运行（开发者）</summary>

```bash
git clone https://github.com/RavenWangChina/yuanzhu.git
cd yuanzhu/server
python -m venv .venv && .venv/Scripts/pip install -e ".[dev]"
.venv/Scripts/yuanzhu-server           # 或 python -m pytest tests/ 跑 142 个测试
```
</details>

Web 控制台前端源码在 `web/`（Vite+Vue3，构建产物由 FastAPI 托管）；模型接入零配置：网关自动导入 dsh 已配的 provider（天翼云等，OpenAI 兼容协议全家桶）；自定义端点用 `YUANZHU_PROVIDER_n_*` 环境变量；估费价目用 `YUANZHU_MODEL_PRICES`（JSON）。

打开首页即**深度问答**：问一个问题自动走六步流水线（澄清→双视角并行→审查→裁决→人审采纳）。

## 文档导航

| 文档 | 内容 |
|------|------|
| **[docs/使用场景与接入形态.md](docs/使用场景与接入形态.md)** | **入门首选：三种用户怎么用 + Claude Code 接入** |
| **[docs/模板开发指南.md](docs/模板开发指南.md)** | **开发者：一句话铸造 / 手工四段式教程** |
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
- **评测集守门**：模板自带 YAML 声明式用例——dry-run 结构校验 → evals 行为验证 → 人审（"无测试不合并"的工作流版）
- **知识库**：洞见/答案/域对象/forge 模板——生成的一切有统一入口
- **执行底座无关**：方法论资产不绑定任何 AI 执行框架
- **解放人力，不是替代人力**

## License

**AGPL-3.0**（强保护协议：防闭源白嫖，为企业版保留商业授权空间——ADR-009 决策）。

## 致谢

本项目引用了周志明（icyfenix）先生《设计机器学习应用系统》等外部来源，完整清单见 [docs/致谢与引用出处.md](docs/致谢与引用出处.md)。
