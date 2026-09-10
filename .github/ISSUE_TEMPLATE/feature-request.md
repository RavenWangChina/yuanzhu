name: 功能建议
description: 想要新能力？想接入新场景？说说你的想法
labels: ["enhancement"]
body:
  - type: textarea
    id: problem
    attributes:
      label: 你想解决什么问题？
      description: 描述你的使用场景和痛点（比直接说"想要 XX 功能"更有帮助）
      placeholder: |
        我是做 XX 工作的，每天要……，现在……很麻烦
    validations:
      required: true

  - type: textarea
    id: idea
    attributes:
      label: 你的设想
      description: 如果有个……就好了。不成熟也没关系，一起讨论
    validations:
      required: false

  - type: dropdown
    id: area
    attributes:
      label: 相关方向
      options:
        - 新领域模板（QA 之外的工作流）
        - 对话学习（从聊天记录学工作流）
        - agent 接入（MCP/Claude Code/其他 AI 工具）
        - 部署形态（单机/企业/云端）
        - 使用体验（界面/CLI）
        - 其他
    validations:
      required: true
