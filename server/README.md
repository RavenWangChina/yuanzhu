# 元铸工坊 yuanzhu

**把最佳实践铸成可治理的 AI 工作流资产——AI 提议，人拍板。**

一台独立运行的引擎（本体层 + 模板 + 工作流 + 审批），三种用法：

- **深度问答**：问一个问题自动走六步流水线（澄清→双视角并行作答→独立审查→综合裁决→人审采纳）
- **一句话铸模板**：描述你的日常工作，AI 生成完整工作流模板，评测自动守门
- **agent 接入**：Claude Code 等经 MCP 直连（`claude mcp add yuanzhu http://127.0.0.1:8600/mcp`）

## 安装与启动

```bash
pip install yuanzhu
yuanzhu-server          # 打开 http://127.0.0.1:8600
```

首启自动注册内置模板（深度问答/AIQA 测试/会议追踪），零配置可用。
CLI 同装：`yuanzhu status / pending / templates / forge "你的工作描述"`。

模型接入：自动读取 dsh 已配 provider；或用环境变量接任意 OpenAI 兼容端点
（`YUANZHU_PROVIDER_n_{NAME,BASE_URL,API,KEY,MODELS}`）。

## 核心概念

| 概念 | 一句话 |
|------|--------|
| 本体层 | 你的业务对象（名词）+ 受治理的动作（动词）——业务世界的数字孪生 |
| staged writes | AI 的所有写操作先进待审区，人批准才生效 |
| 四段式模板 | 对象模型+动作库+工作流+评测集——可安装的"专家经验" |

## 许可

AGPL-3.0。文档与源码：<https://github.com/RavenWangChina/yuanzhu>
