# dsh-plugin-yuanzhu

[元铸工坊 SOSOFAST](https://github.com/RavenWangChina/yuanzhu) 的 dsh 插件——把治理层接进 dsh 启动的 agent。

## 权限模型（治理不穿透）

| 工具 | 类型 | 说明 |
|------|------|------|
| `yuanzhu_pending` | 读 | 列待审 staged 动作 |
| `yuanzhu_actions` | 读 | 列可用动作（发现能力） |
| `yuanzhu_query` | 读 | 按对象类型查本体层 |
| `yuanzhu_execute` | 写提交 | L1 自动生效 / L2 进 staged 待审 |
| `yuanzhu_forge` | 铸造 | 一句话铸工作流模板（内置三道守门） |

**审批（approve/reject）刻意不暴露给 agent**——AI 不能批自己的写，人审在元铸工坊 Web/CLI 侧完成。

## 安装

```bash
# 前置：元铸工坊服务已启动（pip install yuanzhu && yuanzhu-server）
dsh --profile <name> plugin add dsh-plugin-yuanzhu   # 从 npm
```

环境变量：

- `YUANZHU_URL`（默认 `http://127.0.0.1:8600`）
- `YUANZHU_TOKEN`（服务端配置了 api_token 时必填）
