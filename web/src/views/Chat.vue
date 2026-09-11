<template>
  <div class="chat-wrap">
    <div class="chat-scroll" ref="scrollRef">
      <div v-if="messages.length === 0" class="chat-hero">
        <h2>有什么在纠结的？</h2>
        <p>每个问题走六步流水线：澄清 → 双视角并行 → 审查 → 裁决 → 你来采纳。
           问过的会变成你的知识库，越用越懂你。</p>
        <div class="hero-examples">
          <button v-for="ex in examples" :key="ex" class="btn" @click="question = ex">{{ ex }}</button>
        </div>
      </div>

      <div v-for="(m, i) in messages" :key="i" class="msg" :class="m.role">
        <div class="bubble">
          <template v-if="m.role === 'user'">{{ m.text }}</template>
          <template v-else>
            <div v-if="m.loading" class="loading-line">{{ m.phase }}<span class="dots">…</span></div>
            <template v-else>
              <div v-if="m.error" class="error-box">{{ m.error }}</div>
              <div v-if="m.insightCount" class="insight-hint">📚 已参考你 {{ m.insightCount }} 条历史洞见</div>
              <div class="answer-body">{{ m.text }}</div>
              <details v-if="m.details" class="process">
                <summary>看思考过程（双视角/审查）</summary>
                <div v-for="(v, k) in m.details" :key="k" class="stage">
                  <b>{{ STAGE_NAMES[k] || k }}</b>
                  <div class="stage-body">{{ v }}</div>
                </div>
              </details>
              <div class="msg-actions">
                <button v-if="!m.adopted && m.execId" class="btn primary btn-sm" @click="adopt(m)">采纳（沉淀为知识）</button>
                <span v-else-if="m.adopted" class="adopted">✓ 已采纳</span>
              </div>
            </template>
          </template>
        </div>
      </div>
    </div>

    <!-- 工作流建议条（T4：重复模式检测） -->
    <div v-if="suggestion" class="suggestion-bar">
      <span>💡 {{ suggestion.reason }}</span>
      <button class="btn primary btn-sm" :disabled="forging" @click="acceptSuggestion">
        {{ forging ? '铸造中…' : '铸成工作流' }}
      </button>
      <button class="btn btn-sm" @click="suggestion = null">忽略</button>
    </div>

    <div class="chat-input card">
      <textarea v-model="question" rows="2" :disabled="running"
                placeholder="继续问，或换个新问题…（Enter 发送 / Shift+Enter 换行）"
                @keydown.enter.exact.prevent="send"></textarea>
      <button class="btn primary" :disabled="running || !question.trim()" @click="send">
        {{ running ? '思考中' : '提问' }}
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, nextTick } from 'vue'
import { api } from '../api'

interface Message {
  role: 'user' | 'assistant'
  text: string
  loading?: boolean
  phase?: string
  error?: string
  details?: Record<string, string>
  insightCount?: number
  execId?: number | null
  adopted?: boolean
}

const messages = ref<Message[]>([])
const question = ref('')
const running = ref(false)
const scrollRef = ref<HTMLElement>()
const suggestion = ref<any>(null)
const forging = ref(false)

const examples = [
  '我该不该把服务迁到云上？',
  '如何给团队定 AI 工具预算？',
  '这个季度重点做产品还是做市场？',
]

const STAGE_NAMES: Record<string, string> = {
  clarification: '① 澄清',
  ans_a: '② 视角A（推进者）',
  ans_b: '③ 视角B（质疑者·并行）',
  audit: '④ 独立审查',
}

async function send() {
  const q = question.value.trim()
  if (!q || running.value) return
  question.value = ''
  messages.value.push({ role: 'user', text: q })
  // P0 修复：reactive 包裹——push 后对 phase/loading/text 的修改才能触发视图更新
  const aiMsg: Message = reactive({ role: 'assistant', text: '', loading: true, phase: '澄清问题' })
  messages.value.push(aiMsg)
  running.value = true
  await scrollBottom()

  const phases = ['澄清问题', '双视角并行作答', '独立审查', '综合裁决']
  let pi = 0
  const timer = setInterval(() => {
    pi = Math.min(pi + 1, phases.length - 1)
    aiMsg.phase = phases[pi]
  }, 40000)
  try {
    const r = await api.post('/api/workflows/run', {
      domain: 'metaflow', workflow: 'deep-answer',
      params: { question: q }, run_by: 'web-chat',
    })
    const steps = r.steps || {}
    aiMsg.loading = false
    aiMsg.text = steps.verdict?.result || '（无输出）'
    aiMsg.details = {
      clarification: steps.clarification?.result,
      ans_a: steps['view-a']?.result,
      ans_b: steps['view-b']?.result,
      audit: steps.audit?.result,
    }
    aiMsg.execId = steps.save?.exec_id ?? null
    // 差异可视化：本次参考了多少洞见（从澄清步内容推断——有洞见时澄清会提到）
    aiMsg.insightCount = (steps.recall?.result as any[])?.length || 0
  } catch (e: any) {
    aiMsg.loading = false
    aiMsg.error = String(e).replace('Error: ', '')
  } finally {
    clearInterval(timer)
    running.value = false
    await scrollBottom()
  }
  // T4：问完检查重复模式
  await checkPattern()
}

async function adopt(m: Message) {
  if (!m.execId) return
  try {
    await api.post(`/api/metaflow/adopt/${m.execId}`, { adopted_by: 'web-chat' })
    m.adopted = true
  } catch (e: any) {
    m.error = String(e).replace('Error: ', '')
  }
}

// T4：重复模式检测（问答历史 → AI 判断是否例行公事 → 建议铸工作流）
async function checkPattern() {
  try {
    const r = await api.post('/api/metaflow/suggest-workflow', {})
    if (r.suggested) suggestion.value = r
  } catch { /* 静默——建议失败不打扰对话 */ }
}

async function acceptSuggestion() {
  forging.value = true
  try {
    const r = await api.post('/api/templates/forge', { description: suggestion.value.description })
    suggestion.value = null
    messages.value.push({
      role: 'assistant',
      text: r.status === 'published'
        ? `✅ 已铸成工作流「${r.name}」并上架（评测 ${r.evals.passed}/${r.evals.total}）——去模板市场看看`
        : `⚠ 铸成「${r.name}」但评测未全过，留在草稿区（模板市场可重跑）`,
    })
  } catch (e: any) {
    suggestion.value = { reason: '铸造失败：' + String(e).replace('Error: ', '') }
  } finally {
    forging.value = false
    await scrollBottom()
  }
}

async function scrollBottom() {
  await nextTick()
  scrollRef.value?.scrollTo({ top: scrollRef.value.scrollHeight, behavior: 'smooth' })
}

onMounted(() => {
  // 加载历史问答（本体里已采纳的 Answer）
  api.get('/api/objects?domain=metaflow&limit=20').then((objs: any[]) => {
    for (const o of objs.reverse()) {
      if (o.properties?.question && o.properties?.content) {
        messages.value.push({ role: 'user', text: o.properties.question })
        messages.value.push({ role: 'assistant', text: o.properties.content,
          adopted: !!o.properties.adopted_by })   // 按 adopted_by 判断（dogfood 卡点3）
      }
    }
    scrollBottom()
  }).catch(() => {})
})
</script>

<style scoped>
.chat-wrap { display: flex; flex-direction: column; height: calc(100vh - 140px); }
.chat-scroll { flex: 1; overflow-y: auto; padding: 8px 4px; }
.chat-hero { text-align: center; padding: 60px 20px; color: var(--muted); }
.chat-hero h2 { color: var(--text); margin-bottom: 8px; }
.hero-examples { display: flex; gap: 10px; justify-content: center; margin-top: 20px; flex-wrap: wrap; }
.msg { display: flex; margin: 10px 0; }
.msg.user { justify-content: flex-end; }
.bubble { max-width: 78%; padding: 12px 16px; border-radius: 14px; background: var(--card);
  border: 1px solid var(--border); white-space: pre-wrap; word-break: break-all; line-height: 1.65; }
.msg.user .bubble { background: var(--primary); color: #fff; border: none; }
.loading-line { color: var(--muted); }
.dots::after { content: ''; animation: dots 1.5s steps(4) infinite; }
@keyframes dots { 0% { content: ''; } 25% { content: '.'; } 50% { content: '..'; } 75% { content: '...'; } }
.insight-hint { background: #eef4ff; color: var(--primary); font-size: 12px; padding: 4px 10px;
  border-radius: 6px; margin-bottom: 8px; display: inline-block; }
.answer-body { font-size: 14px; }
.process { margin-top: 10px; }
.process summary { cursor: pointer; color: var(--muted); font-size: 13px; }
.stage { margin: 10px 0; }
.stage b { font-size: 12px; color: var(--muted); }
.stage-body { font-size: 13px; background: var(--bg); padding: 8px 12px; border-radius: 8px; margin-top: 4px; }
.msg-actions { margin-top: 10px; }
.btn-sm { padding: 5px 12px; font-size: 13px; }
.adopted { color: var(--success); font-size: 13px; }
.error-box { background: #feecec; color: var(--danger); border-radius: 8px; padding: 10px 14px;
  font-size: 13px; margin-bottom: 8px; word-break: break-all; }
.suggestion-bar { display: flex; align-items: center; gap: 12px; background: #fff8e6;
  border: 1px solid #f0e0b0; padding: 10px 16px; border-radius: 10px; margin: 6px 0; font-size: 13px; }
.suggestion-bar span { flex: 1; }
.chat-input { display: flex; gap: 10px; align-items: flex-end; margin-top: 8px; }
.chat-input textarea { flex: 1; resize: none; border: 1px solid var(--border); border-radius: 10px;
  padding: 10px 14px; font-size: 14px; font-family: inherit; }
</style>
