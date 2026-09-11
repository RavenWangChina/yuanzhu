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
          <template v-if="m.role === 'user'">
            {{ m.text }}
            <div v-if="m.queued" class="queued-tag">已排队（前面的完成后自动发送）</div>
          </template>
          <template v-else-if="m.kind === 'notice'">{{ m.text }}</template>
          <template v-else>
            <div v-if="m.loading" class="loading-line">
              {{ m.phase }}<span class="dots">…</span>
              <div v-if="m.doneCount" class="step-progress">{{ m.doneCount }}/6 步</div>
            </div>
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

              <!-- T3：流内洞见轻确认（采纳后 AI 提议的沉淀） -->
              <div v-if="m.adopted && m.distillCandidates && m.distillCandidates.length" class="distill-box">
                <div class="distill-title">AI 从这个答案提炼了 {{ m.distillCandidates.length }} 条洞见，沉淀吗？</div>
                <div v-for="c in m.distillCandidates" :key="c.id" class="distill-item">
                  <span class="distill-text">{{ c.params.takeaway }}</span>
                  <span v-if="c.handled === 'approved'" class="adopted">✓</span>
                  <template v-else-if="c.handled !== 'rejected'">
                    <button class="btn btn-sm" @click="approveDistill(m, c, true)">沉淀</button>
                    <button class="btn btn-sm" @click="approveDistill(m, c, false)">跳过</button>
                  </template>
                </div>
              </div>
            </template>
          </template>
        </div>
      </div>

      <!-- T4：模式检测一次性提示（教育用户此能力存在） -->
      <div v-if="patternHint && !suggestion" class="notice-line">{{ patternHint }}</div>

      <!-- 工作流建议条 -->
      <div v-if="suggestion" class="suggestion-bar">
        <span>💡 {{ suggestion.reason }}</span>
        <button class="btn primary btn-sm" :disabled="forging" @click="acceptSuggestion">
          {{ forging ? '铸造中…' : '铸成工作流' }}
        </button>
        <button class="btn btn-sm" @click="suggestion = null">忽略</button>
      </div>
    </div>

    <div class="chat-input card">
      <textarea v-model="question" rows="2"
                placeholder="继续问，或换个新问题…（Enter 发送 / Shift+Enter 换行；思考中也可排队提问）"
                @keydown.enter.exact.prevent="send"></textarea>
      <button class="btn primary" :disabled="!question.trim()" @click="send">
        {{ running ? '排队' : '提问' }}
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, nextTick } from 'vue'
import { api } from '../api'

interface DistillCandidate {
  id: number, params: { takeaway: string, [k: string]: any }, handled?: string
}
interface Message {
  role: 'user' | 'assistant'
  text: string
  kind?: 'notice'
  queued?: boolean
  loading?: boolean
  phase?: string
  doneCount?: number
  error?: string
  details?: Record<string, string>
  insightCount?: number
  execId?: number | null
  adopted?: boolean
  distillCandidates?: DistillCandidate[]
}

const messages = ref<Message[]>([])
const question = ref('')
const running = ref(false)
const scrollRef = ref<HTMLElement>()
const suggestion = ref<any>(null)
const forging = ref(false)
const patternHint = ref('')
const queue: string[] = []

const examples = [
  '我该不该把服务迁到云上？',
  '如何给团队定 AI 工具预算？',
  '这个季度重点做产品还是做市场？',
]

const STAGE_NAMES: Record<string, string> = {
  clarification: '① 澄清',
  'view-a': '② 视角A（推进者）',
  'view-b': '③ 视角B（质疑者·并行）',
  ans_a: '② 视角A', ans_b: '③ 视角B',
  audit: '④ 独立审查',
}
const STEP_LABELS: Record<string, string> = {
  recall: '回忆你的知识', clarification: '澄清问题', 'view-a': '视角A作答',
  'view-b': '视角B作答（并行）', audit: '独立审查', verdict: '综合裁决', save: '整理入库',
}

async function send() {
  const q = question.value.trim()
  if (!q) return
  question.value = ''

  if (running.value) {
    queue.push(q)
    messages.value.push(reactive({ role: 'user', text: q, queued: true }))
    return
  }
  await runQuestion(q)
}

async function runQuestion(q: string) {
  messages.value.push(reactive({ role: 'user', text: q }))
  const aiMsg: Message = reactive({ role: 'assistant', text: '', loading: true, phase: '启动流水线', doneCount: 0 })
  messages.value.push(aiMsg)
  running.value = true
  await scrollBottom()

  try {
    const start = await api.post('/api/workflows/run-async', {
      domain: 'metaflow', workflow: 'deep-answer',
      params: { question: q }, run_by: 'web-chat',
    })
    const taskId = start.task_id
    const seenSteps = new Set<string>()

    const poll = window.setInterval(async () => {
      try {
        const st = await api.get(`/api/workflows/status/${taskId}`)
        st.done_steps?.forEach((sid: string) => {
          if (!seenSteps.has(sid)) {
            seenSteps.add(sid)
            aiMsg.doneCount = seenSteps.size
            aiMsg.phase = STEP_LABELS[sid] || `完成 ${sid}`
          }
        })
      } catch { /* 轮询失败静默重试 */ }
    }, 2000)

    let final: any = null
    for (let i = 0; i < 240; i++) {
      await new Promise(r => setTimeout(r, 2000))
      const st = await api.get(`/api/workflows/status/${taskId}`)
      if (st.done) { final = st; break }
    }
    clearInterval(poll)

    if (!final) throw new Error('超时（8 分钟）')
    if (final.status === 'error') throw new Error(final.error || '流水线失败')

    const steps = final.result?.steps || {}
    aiMsg.loading = false
    aiMsg.phase = ''
    aiMsg.text = steps.verdict?.result || '（无输出）'
    aiMsg.details = {
      clarification: steps.clarification?.result,
      ans_a: (steps['view-a'] || steps.ans_a)?.result,
      ans_b: (steps['view-b'] || steps.ans_b)?.result,
      audit: steps.audit?.result,
    }
    aiMsg.execId = steps.save?.exec_id ?? null
    aiMsg.insightCount = (steps.recall?.result as any[])?.length || 0
  } catch (e: any) {
    aiMsg.loading = false
    aiMsg.error = String(e).replace('Error: ', '')
  } finally {
    running.value = false
    await scrollBottom()
  }

  await checkPattern()
  if (queue.length) {
    const next = queue.shift()!
    const qm = messages.value.filter(m => m.text === next && m.queued).pop()
    if (qm) qm.queued = false
    await runQuestion(next)
  }
}

async function adopt(m: Message) {
  if (!m.execId) return
  try {
    await api.post(`/api/metaflow/adopt/${m.execId}`, { adopted_by: 'web-chat' })
    m.adopted = true
    const pending = await api.get('/api/staged/pending')
    m.distillCandidates = pending
      .filter((p: any) => p.action?.includes('DistillInsight') && p.staged_by === 'auto-distill')
      .map((p: any) => reactive({ id: p.id, params: p.params }))
  } catch (e: any) {
    m.error = String(e).replace('Error: ', '')
  }
}

async function approveDistill(m: Message, c: DistillCandidate, approve: boolean) {
  try {
    if (approve) {
      await api.post(`/api/staged/${c.id}/approve`, { reviewed_by: 'web-chat', review_comment: '流内沉淀' })
      c.handled = 'approved'
    } else {
      await api.post(`/api/staged/${c.id}/reject`, { reviewed_by: 'web-chat', review_comment: '跳过' })
      c.handled = 'rejected'
    }
  } catch (e: any) {
    m.error = String(e).replace('Error: ', '')
  }
}

async function checkPattern() {
  try {
    const r = await api.post('/api/metaflow/suggest-workflow', {})
    if (r.suggested) {
      suggestion.value = r
      patternHint.value = ''
    } else if (r.reason?.includes('不足')) {
      patternHint.value = 'ℹ️ 我会留意重复出现的问题——同类问题问满几次，会建议把它铸成可复用的工作流'
      setTimeout(() => (patternHint.value = ''), 8000)
    }
  } catch { /* 静默 */ }
}

async function acceptSuggestion() {
  forging.value = true
  try {
    const r = await api.post('/api/templates/forge', { description: suggestion.value.description })
    suggestion.value = null
    messages.value.push(reactive({
      role: 'assistant', kind: 'notice',
      text: r.status === 'published'
        ? `✅ 已铸成工作流「${r.name}」并上架——去模板市场看看`
        : `⚠ 铸成「${r.name}」但评测未全过，留在草稿区（模板市场可重跑）`,
    }))
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
  api.get('/api/objects?domain=metaflow&limit=20').then((objs: any[]) => {
    for (const o of objs.reverse()) {
      if (o.properties?.question && o.properties?.content) {
        messages.value.push({ role: 'user', text: o.properties.question })
        messages.value.push({ role: 'assistant', text: o.properties.content,
          adopted: !!o.properties.adopted_by })
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
.queued-tag { font-size: 12px; opacity: .8; margin-top: 4px; }
.notice-line { text-align: center; color: var(--muted); font-size: 12px; padding: 4px; }
.loading-line { color: var(--muted); }
.step-progress { font-size: 12px; color: var(--primary); margin-top: 4px; }
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
.distill-box { background: #f6fbf6; border: 1px solid #cde8cd; border-radius: 10px; padding: 10px 14px; margin-top: 10px; }
.distill-title { font-size: 13px; color: var(--success); margin-bottom: 8px; }
.distill-item { display: flex; align-items: center; gap: 8px; margin: 6px 0; font-size: 13px; }
.distill-text { flex: 1; }
.error-box { background: #feecec; color: var(--danger); border-radius: 8px; padding: 10px 14px;
  font-size: 13px; margin-bottom: 8px; word-break: break-all; }
.suggestion-bar { display: flex; align-items: center; gap: 12px; background: #fff8e6;
  border: 1px solid #f0e0b0; padding: 10px 16px; border-radius: 10px; margin: 6px 0; font-size: 13px; }
.suggestion-bar span { flex: 1; }
.chat-input { display: flex; gap: 10px; align-items: flex-end; margin-top: 8px; }
.chat-input textarea { flex: 1; resize: none; border: 1px solid var(--border); border-radius: 10px;
  padding: 10px 14px; font-size: 14px; font-family: inherit; }
</style>
