<template>
  <div>
    <h1 class="page-title">待审中心</h1>
    <p class="page-desc">AI 提出的写操作在这里等你确认——批准即生效，拒绝需说明理由</p>

    <div v-if="loading" class="empty">加载中…</div>
    <div v-else-if="loadError" class="empty card" style="color:var(--danger)">{{ loadError }}</div>
    <div v-else-if="items.length === 0" class="empty card">🎉 没有待审事项</div>

    <div v-for="item in items" :key="item.id" class="card">
      <!-- 动作：友好描述为主，技术名辅助（H2 卡点 2） -->
      <div class="action-line">
        <b>{{ friendlyAction(item) }}</b>
        <span class="tech-name">{{ item.action }}（#{{ item.id }}）</span>
      </div>
      <div class="kv">
        <span class="k">提出者</span>
        <span class="v">{{ item.staged_by }}</span>
      </div>

      <!-- 参数友好渲染（H2 卡点 1）：中文键名 + 长文本块，不再显示原始 JSON -->
      <div v-for="(val, key) in friendlyParams(item.params)" :key="key" class="kv">
        <span class="k">{{ key }}</span>
        <span class="v">{{ shortText(val) }}</span>
      </div>
      <div v-for="key in longTextKeys(item.params)" :key="'lt-' + key" class="text-block">
        <div class="text-block-title">{{ labelOf(key) }}</div>
        <div class="text-block-body">{{ item.params[key] }}</div>
      </div>

      <div v-if="item.before" class="snapshot">
        <div v-for="(val, key) in item.before" :key="key" class="kv">
          <span class="k">{{ labelOf(String(key)) }}</span>
          <span class="v">{{ val }}</span>
        </div>
      </div>

      <div class="actions" style="margin-top: 12px">
        <input
          v-model="comments[item.id]"
          class="comment"
          placeholder="审批意见（拒绝时必填）"
        />
        <button class="btn primary" @click="approve(item.id)">批准</button>
        <button class="btn danger" @click="reject(item.id)">拒绝</button>
      </div>
    </div>

    <div v-if="toast" class="toast" :class="{ error: toastIsError }">{{ toast }}</div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { api } from '../api'

interface PendingItem {
  id: number
  action: string
  action_description?: string | null
  params: Record<string, unknown>
  staged_by: string
  staged_at: string
  before: Record<string, unknown> | null
}

const items = ref<PendingItem[]>([])
const comments = ref<Record<number, string>>({})
const loading = ref(true)
const loadError = ref('')
const toast = ref('')
const toastIsError = ref(false)

// 参数中文键名（H2：小白可读）；未映射的键原样显示
const LABELS: Record<string, string> = {
  title: '标题', name: '名称', status: '状态', severity: '严重程度',
  priority: '优先级', module_name: '所属模块', reproduce_steps: '复现步骤',
  content: '内容', resolution: '处理说明', comment: '备注', kind: '类型',
  owner: '负责人', description: '描述',
}
// 隐藏纯技术参数（对审批决策无意义）
const HIDDEN = new Set(['object_id', 'exec_id'])
// 长文本键：单独渲染为文本块（不挤在键值行里）
const LONG_TEXT = new Set(['content', 'reproduce_steps', 'description', 'steps'])

function labelOf(key: string): string {
  return LABELS[key] || key
}

function friendlyAction(item: PendingItem): string {
  return item.action_description || item.action
}

function friendlyParams(params: Record<string, unknown>): Record<string, unknown> {
  const out: Record<string, unknown> = {}
  for (const [k, v] of Object.entries(params || {})) {
    if (HIDDEN.has(k) || LONG_TEXT.has(k)) continue
    if (v === null || v === undefined || v === '') continue
    out[labelOf(k)] = v
  }
  return out
}

function longTextKeys(params: Record<string, unknown>): string[] {
  return Object.keys(params || {}).filter(
    k => LONG_TEXT.has(k) && params[k] !== null && params[k] !== undefined && params[k] !== '',
  )
}

function shortText(v: unknown): string {
  const s = String(v)
  return s.length > 60 ? s.slice(0, 60) + '…' : s
}

function showToast(msg: string, isError = false) {
  toast.value = msg
  toastIsError.value = isError
  setTimeout(() => (toast.value = ''), 2500)
}

async function load() {
  loading.value = true
  try {
    items.value = await api.get('/api/staged/pending')
  } catch (e) {
    loadError.value = `待审列表加载失败：${String(e).replace('Error: ', '')}`
  } finally {
    loading.value = false
  }
}

async function approve(id: number) {
  try {
    await api.post(`/api/staged/${id}/approve`, {
      reviewed_by: 'web-reviewer',
      review_comment: comments.value[id] || '同意',
    })
    showToast('已批准并生效')
    await load()
  } catch (e) {
    showToast(String(e), true)
  }
}

async function reject(id: number) {
  const comment = comments.value[id]
  if (!comment) {
    showToast('拒绝必须填写理由', true)
    return
  }
  try {
    await api.post(`/api/staged/${id}/reject`, {
      reviewed_by: 'web-reviewer',
      review_comment: comment,
    })
    showToast('已拒绝')
    await load()
  } catch (e) {
    showToast(String(e), true)
  }
}

onMounted(load)
</script>

<style scoped>
.action-line {
  display: flex; align-items: baseline; gap: 10px;
  margin-bottom: 8px; font-size: 15px;
}
.tech-name {
  color: var(--muted); font-size: 12px; font-family: ui-monospace, Consolas, monospace;
}
.text-block {
  background: var(--bg); border-radius: 8px; padding: 10px 14px; margin-top: 8px;
}
.text-block-title {
  color: var(--muted); font-size: 12px; margin-bottom: 4px;
}
.text-block-body {
  white-space: pre-wrap; font-size: 13px; line-height: 1.6; word-break: break-all;
}
</style>
