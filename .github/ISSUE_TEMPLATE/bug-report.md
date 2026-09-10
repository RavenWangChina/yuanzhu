name: Bug 报告
description: 发现了问题？请带上复现步骤和环境信息，帮我们快速定位
labels: ["bug"]
body:
  - type: textarea
    id: what-happened
    attributes:
      label: 发生了什么？
      description: 简述问题现象，以及你预期应该是什么样子
      placeholder: |
        现象：审批一条动作后……
        预期：应该……
    validations:
      required: true

  - type: textarea
    id: steps
    attributes:
      label: 复现步骤
      description: 从干净状态开始，一步步怎么触发的
      placeholder: |
        1. python -m uvicorn yuanzhu.main:app --port 8600
        2. 打开 http://127.0.0.1:8600/templates 点「使用」
        3. ……
    validations:
      required: true

  - type: dropdown
    id: component
    attributes:
      label: 出问题的部分
      options:
        - Web 控制台（待审中心/模板市场/…）
        - CLI（yuanzhu 命令）
        - MCP / agent 接入（Claude Code 等）
        - 工作流执行（ai_step/action_step）
        - 模板（AIQA 四段式）
        - 对话学习（导入/提炼）
        - 模型网关（多协议接入）
        - 安装/启动
        - 其他
    validations:
      required: true

  - type: input
    id: env
    attributes:
      label: 环境信息
      description: 操作系统 / Python 版本 / 部署模式（单机 or 服务器）
      placeholder: "Windows 11 / Python 3.12 / 单机模式"

  - type: textarea
    id: logs
    attributes:
      label: 相关日志或截图
      description: 终端报错、浏览器 Console、截图都可以（注意别贴 API key）
      render: shell
