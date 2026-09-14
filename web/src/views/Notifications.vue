<template>
  <div>
    <h1 class="page-title">通知中心</h1>
    <p class="page-desc">推衍提议、自举状态与最近活动——你的主动助手</p>

    <!-- 自举开关 -->
    <div class="card bootstrap-card" :class="{ on: bootstrapEnabled }">
      <div style="display:flex; justify-content:space-between; align-items:center">
        <div>
          <b>自举模式</b>
          <div style="color:var(--muted); font-size:13px; margin-top:2px">
            {{ bootstrapEnabled ? '开启中——行为记录与推衍引擎已激活' : '已关闭——行为不被记录，推衍引擎暂停' }}
          </div>
        </div>
        <button class="btn" :class="bootstrapEnabled ? 'danger' : 'primary'" @click="toggleBootstrap">
          {{ bootstrapEnabled ? '关闭' : '开启' }}
        </button>
      </div>
    </div>

    <!-- 推衍提议 -->
    <h3>💡 推衍提议（{{ pendingProps.length }} 条待审）</h3>
    <div v-if="loadingProps" class="empty">加载中…</div>
    <div v-else-if="pendingProps.length === 0" class="empty card">
      暂无新提议——多问几个问题、采纳几个答案，推衍引擎会发现你的模式
    </div>
    <div v-for="p in pendingProps" :key="p.id" class="card prop-card">
      <div class="prop-header">
        <span class="badge" :class="p.type">{{ typeLabel(p.type) }}</span>
        <span class="prop-confidence">置信度 {{ (p.confidence * 100).toFixed(0) }}%</span>
      </div>
      <div class="prop-insight">{{ p.insight }}</div>
      <div v-if="p.advice" class="prop-advice">建议：{{ p.advice }}</div>
      <div v-if="p.deliverable_draft" class="prop-draft">交付物：{{ p.deliverable_draft }}</div>
      <div class="prop-actions">
        <button class="btn primary btn-sm" @click="acceptProp(p.id)">采纳</button>
        <button class="btn btn-sm" @click="dismissProp(p.id)">忽略</button>
      </div>
    </div>

    <!-- 已处理的提议 -->
    <details v-if="resolvedProps.length" style="margin-top:12px">
      <summary style="cursor:pointer; color:var(--muted); font-size:13px">
        已处理（{{ resolvedProps.length }} 条）
      </summary>
      <div v-for="p in resolvedProps" :key="p.id" class="card" style="margin-top:6px; opacity:0.7">
        <span class="badge" :class="p.status === 'accepted' ? 'applied' : 'offline'">
          {{ p.status === 'accepted' ? '✓ 已采纳' : '已忽略' }}
        </span>
        <span style="margin-left:8px; font-size:13px">{{ p.insight.slice(0, 60) }}…</span>
      </div>
    </details>

    <!-- 最近活动 -->
    <h3 style="margin-top:20px">📊 最近活动</h3>
    <div class="card" style="padding:0">
      <div v-if="behaviors.length === 0" class="empty">暂无活动记录（开启自举后自动记录）</div>
      <div v-for="b in behaviors" :key="b.id" class="behavior-line">
        <span class="behavior-action" :class="b.action">{{ actionIcon(b.action) }}</span>
        <span class="behavior-text">{{ behaviorText(b) }}</span>
        <span class="behavior-time">{{ fmtTime(b.created_at) }}</span>
      </div>
    </div>

    <!-- 知识库统计 -->
    <h3 style="margin-top:20px">📚 知识库</h3>
    <div class="stats-row">
      <div class="card stat-card">
        <div class="stat-num">{{ stats.insights }}</div>
        <div class="stat-label">洞见</div>
      </div>
      <div class="card stat-card">
        <div class="stat-num">{{ stats.answers }}</div>
        <div class="stat-label">答案</div>
      </div>
      <div class="card stat-card">
        <div class="stat-num">{{ stats.templates }}</div>
        <div class="stat-label">模板</div>
      </div>
    </div>

    <div v-if="toast" class="toast" :class="{ error: toastError }">{{ toast }}</div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { api } from '../api'

const bootstrapEnabled = ref(false)
const loadingProps = ref(true)
const pendingProps = ref<any[]>([])
const resolvedProps = ref<any[]>([])
const behaviors = ref<any[]>([])
const stats = ref({ insights: 0, answers: 0, templates: 0 })
const toast = ref('')
const toastError = ref(false)

const TYPE_LABELS: Record<string, string> = {
  workflow_suggestion: '工作流建议',
  knowledge_gap: '知识缺口',
  pattern_insight: '行为模式',
  procedural_hint: '工具提示',
}

function typeLabel(t: string) { return TYPE_LABELS[t] || t }

function actionIcon(a: string) {
  return { ask: '💬', adopt: '✓', forge: '🔨', approve: '👍', reject: '❌' }[a] || '•'
}

function behaviorText(b: any) {
  const d = b.detail || {}
  if (b.action === 'ask') return `提问：${String(d.question || '').slice(0, 40)}`
  if (b.action === 'adopt') return `采纳了答案`
  if (b.action === 'forge') return `铸造模板：${String(d.description || '').slice(0, 30)}`
  return `${b.action} ${b.target_name || ''}`
}

function fmtTime(t: string) {
  if (!t) return ''
  const d = new Date(t)
  const diff = (Date.now() - d.getTime()) / 1000
  if (diff < 60) return '刚刚'
  if (diff < 3600) return `${Math.floor(diff / 60)} 分钟前`
  if (diff < 86400) return `${Math.floor(diff / 3600)} 小时前`
  return d.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' })
}

function showToast(msg: string, isErr = false) {
  toast.value = msg
  toastError.value = isErr
  setTimeout(() => (toast.value = ''), 2500)
}

async function toggleBootstrap() {
  try {
    const r = await api.post('/bootstrap/toggle', {})
    bootstrapEnabled.value = r.enabled
    showToast(r.message)
  } catch (e: any) { showToast(String(e), true) }
}

async function acceptProp(id: number) {
  try {
    const r = await api.post(`/propositions/${id}/accept`, {})
    showToast(`已采纳：${r.action || '完成'}`)
    await loadProps()
  } catch (e: any) { showToast(String(e), true) }
}

async function dismissProp(id: number) {
  try {
    await api.post(`/propositions/${id}/dismiss`, {})
    showToast('已忽略')
    await loadProps()
  } catch (e: any) { showToast(String(e), true) }
}

async function loadProps() {
  loadingProps.value = true
  try {
    pendingProps.value = await api.get('/propositions?status=pending')
    const accepted = await api.get('/propositions?status=accepted')
    const dismissed = await api.get('/propositions?status=dismissed')
    resolvedProps.value = [...accepted, ...dismissed]
  } finally { loadingProps.value = false }
}

onMounted(async () => {
  try {
    const st = await api.get('/bootstrap/status')
    bootstrapEnabled.value = st.enabled
    await Promise.all([loadProps(), loadBehaviors(), loadStats()])
  } catch (e) { console.error(e) }
})

async function loadBehaviors() {
  try { behaviors.value = await api.get('/behavior/recent?limit=15') } catch {}
}

async function loadStats() {
  try {
    const objs = await api.get('/objects?domain=metaflow&limit=100')
    stats.value.insights = objs.filter((o: any) => o.object_type?.name === 'Insight').length
    stats.value.answers = objs.filter((o: any) => o.object_type?.name === 'Answer').length
    const tpls = await api.get('/templates')
    stats.value.templates = tpls.length
  } catch {}
}
</script>

<style scoped>
.bootstrap-card { border-left: 3px solid var(--muted); }
.bootstrap-card.on { border-left-color: var(--success); }
h3 { margin: 16px 0 8px; font-size: 15px; }
.prop-card { border-left: 3px solid var(--primary); }
.prop-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.prop-confidence { color: var(--muted); font-size: 12px; }
.prop-insight { font-size: 14px; line-height: 1.5; }
.prop-advice { font-size: 13px; color: var(--primary); margin-top: 6px; }
.prop-draft { font-size: 12px; color: var(--muted); margin-top: 4px; font-style: italic; }
.prop-actions { margin-top: 10px; display: flex; gap: 8px; }
.badge { display: inline-block; padding: 2px 10px; border-radius: 999px; font-size: 12px; }
.badge.workflow_suggestion { background: #e8f0ff; color: var(--primary); }
.badge.knowledge_gap { background: #fff3e0; color: #ff8800; }
.badge.pattern_insight { background: #f3e5f5; color: #9c27b0; }
.badge.procedural_hint { background: #e8f5e9; color: #2e7d32; }
.badge.applied { background: #e8f7e8; color: var(--success); }
.badge.offline { background: #f0f0f0; color: var(--muted); }
.behavior-line { display: flex; align-items: center; gap: 10px; padding: 10px 16px; border-bottom: 1px solid var(--border); font-size: 13px; }
.behavior-action { font-size: 16px; }
.behavior-text { flex: 1; color: var(--text); }
.behavior-time { color: var(--muted); font-size: 12px; }
.stats-row { display: flex; gap: 12px; }
.stat-card { flex: 1; text-align: center; padding: 16px; }
.stat-num { font-size: 24px; font-weight: 600; color: var(--primary); }
.stat-label { color: var(--muted); font-size: 13px; margin-top: 4px; }
.btn-sm { padding: 5px 12px; font-size: 13px; }
</style>
