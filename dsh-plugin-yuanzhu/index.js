// 元铸工坊 (yuanzhu) dsh 插件——把治理层接进 dsh 启动的 agent
// 权限模型：只暴露 读 + 写提交（staged）。approve/reject 不给 agent——
// AI 不能批自己的写，人审在元铸工坊 Web/CLI 侧完成（治理不穿透）。
'use strict'

const BASE = process.env.YUANZHU_URL || 'http://127.0.0.1:8600'
const TOKEN = process.env.YUANZHU_TOKEN || ''

async function api(path, opts = {}) {
  const headers = { 'Content-Type': 'application/json', ...(opts.headers || {}) }
  if (TOKEN) headers['Authorization'] = `Bearer ${TOKEN}`
  const r = await fetch(`${BASE}${path}`, { ...opts, headers })
  const text = await r.text()
  if (!r.ok) throw new Error(`元铸工坊 HTTP ${r.status}: ${text.slice(0, 300)}`)
  try { return JSON.parse(text) } catch { return { raw: text.slice(0, 2000) } }
}

const render = (_a, v) => [{
  type: 'text',
  text: JSON.stringify(v, null, 1).slice(0, 4000),
}]

exports.name = 'yuanzhu'
exports.inject = ['tools']

exports.apply = (ctx) => {
  ctx.tools.register({
    name: 'yuanzhu_pending',
    description: '列出元铸工坊待审的 staged 动作（AI 提交的写操作待人拍板）。只读。',
    parameters: {},
    output: { schema: { type: 'object' }, render },
    async execute() {
      return { pending: await api('/api/staged/pending') }
    },
  })

  ctx.tools.register({
    name: 'yuanzhu_actions',
    description: '列出元铸工坊可用的动作类型（按域分组，含中文说明与自主性等级 L1自动/L2人审）。只读，用于发现能做什么。',
    parameters: {
      domain: { type: 'string', required: false, description: '按域过滤（如 aiqa/metaflow），省略列全部' },
    },
    output: { schema: { type: 'object' }, render },
    async execute(args) {
      const q = args.domain ? `?domain=${encodeURIComponent(args.domain)}` : ''
      return { actions: await api(`/api/actions/types${q}`) }
    },
  })

  ctx.tools.register({
    name: 'yuanzhu_query',
    description: '按对象类型查询元铸工坊本体层的对象（只读）。对象类型可先用 yuanzhu_actions 旁的 /api/objects/types 发现，工具名为 query_{domain}_{type} 小写。',
    parameters: {
      tool: { type: 'string', required: true, description: '查询工具名，如 query_aiqa_bug' },
      filter: { type: 'object', required: false, description: '属性过滤，如 {"status":"Open"}' },
      limit: { type: 'number', required: false, description: '返回条数，默认 10' },
    },
    output: { schema: { type: 'object' }, render },
    async execute(args) {
      return api('/mcp', {
        method: 'POST',
        body: JSON.stringify({
          jsonrpc: '2.0', id: 1, method: 'tools/call',
          params: { name: args.tool, arguments: { filter: args.filter || {}, limit: args.limit || 10 } },
        }),
      })
    },
  })

  ctx.tools.register({
    name: 'yuanzhu_execute',
    description: '执行元铸工坊的一个动作（写操作）。L1 自动生效；L2 只会进入 staged 待审，等人批准。动作名与参数 schema 用 yuanzhu_actions 查。',
    parameters: {
      action: { type: 'string', required: true, description: '执行工具名，如 execute_aiqa_createbug' },
      arguments: { type: 'object', required: true, description: '动作参数（按 schema）' },
    },
    output: { schema: { type: 'object' }, render },
    async execute(args) {
      const r = await api('/mcp', {
        method: 'POST',
        body: JSON.stringify({
          jsonrpc: '2.0', id: 1, method: 'tools/call',
          params: { name: args.action, arguments: args.arguments },
        }),
      })
      // 解包 MCP content 给 agent 看结论
      try {
        const inner = JSON.parse(r.result.content[0].text)
        return { status: inner.status || 'ok', exec_id: inner.exec_id, detail: inner }
      } catch { return r }
    },
  })

  ctx.tools.register({
    name: 'yuanzhu_forge',
    description: '一句话铸造工作流模板（AI 生成四段式→结构校验→冒烟评测→全过自动上架）。描述要含：谁/做什么/产出什么。耗时约 30-60 秒。',
    parameters: {
      description: { type: 'string', required: true, description: '日常工作描述，第一人称，如：我每周五收集各小组进展汇总成周报' },
    },
    output: { schema: { type: 'object' }, render },
    async execute(args) {
      return api('/api/templates/forge', {
        method: 'POST',
        body: JSON.stringify({ description: args.description }),
      })
    },
  })
}
