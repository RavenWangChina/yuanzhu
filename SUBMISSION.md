# yuanzhu 提交材料（官方 marketplace + MCP 目录站）

> 用途：以下英文材料按各平台提交表单的字段组织，直接复制粘贴。中文注释仅供你对照。

---

## ① Anthropic 官方插件目录

**提交入口**：https://clau.de/plugin-directory-submission （需浏览器登录 Anthropic 账号）

**Plugin name**
```
yuanzhu
```

**Repository URL**
```
https://github.com/RavenWangChina/yuanzhu
```

**Short description**（一句话）
```
Turn recurring work into governed AI workflow assets — one-sentence template forging, staged writes (AI proposes, humans approve), and evals-gated publishing.
```

**Long description**
```
Yuanzhu (元铸工坊, "Meta-Forge Workshop") is a governance layer for AI-assisted teams. It lets any Claude Code session forge recurring work into versioned, testable workflow assets:

- One-sentence forging: describe a routine task → AI generates a four-part template (object model, action library, workflow, evals) → three quality gates (structural dry-run, workflow smoke test, evals) before it ships.
- Staged writes: every AI write action lands in a review queue. L1 actions auto-apply; L2 actions wait for human approval with optimistic locking. Approvals never leak back to the agent.
- MCP-native: the ontology layer (objects, links, actions) is exposed via standard MCP Streamable HTTP, so external agents query and act under the same governance.
- Inference engine: cross-analyzes behavior logs, knowledge, and templates (three-memory architecture) to proactively suggest new workflows and knowledge gaps.

Install: `claude plugin marketplace add RavenWangChina/yuanzhu` then `claude plugin install yuanzhu@yuanzhu`. Requires a local `yuanzhu-server` (pip install yuanzhu). AGPL-3.0.
```

**Category**
```
Workflow / Knowledge management
```

---

## ② MCP 目录站（PulseMCP / mcpservers.org / Glama）

**入口**：
- https://www.pulsemcp.com/submit
- https://mcpservers.org/submit
- https://glama.ai/mcp/servers （右上 Submit）

**Server name**
```
yuanzhu
```

**GitHub / Repository**
```
https://github.com/RavenWangChina/yuanzhu
```

**Description**
```
Governed workflow-asset platform for AI agents. Exposes an ontology layer (typed objects, links, governed actions) over standard MCP Streamable HTTP. AI reads and writes go through staged-writes governance: L1 actions auto-apply, L2 actions queue for human approval. Includes one-sentence template forging (object model + actions + workflow + evals) with three quality gates, and an inference engine that proactively proposes workflows from behavior patterns.

Tools: query_{domain}_{type} (read objects), execute_{domain}_{action} (staged writes), list_pending_approvals, approve_action, reject_action.
```

**Transport**
```
Streamable HTTP (http://127.0.0.1:8600/mcp, self-hosted)
```

**Installation**
```
pip install yuanzhu
yuanzhu-server    # starts FastAPI on :8600 with /mcp endpoint
# Claude Code: claude plugin marketplace add RavenWangChina/yuanzhu
#              claude plugin install yuanzhu@yuanzhu
```

**Auth**（若表单问）
```
Optional Bearer token via api_token setting; header `Authorization: Bearer <token>`.
```

**License**
```
AGPL-3.0
```

---

## ③ npm（dsh-plugin-yuanzhu）——可选，dsh 生态正式发布

本地 workspace 验证已通过。正式发布需 npm 账号：

```bash
cd dsh-plugin-yuanzhu
npm publish --access public
```

发完即可 `dsh --profile <name> plugin add dsh-plugin-yuanzhu`。
