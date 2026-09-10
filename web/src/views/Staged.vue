<template>
  <div>
    <h1 class="page-title">待审中心</h1>
    <p class="page-desc">AI 提出的写操作在这里等你确认——批准即生效，拒绝需说明理由</p>

    <div v-if="loading" class="empty">加载中…</div>
    <div v-else-if="items.length === 0" class="empty card">🎉 没有待审事项</div>

    <div v-for="item in items" :key="item.id" class="card">
      <div class="kv">
        <span class="k">动作</span>
        <span class="v"><b>{{ item.action }}</b>（#{{ item.id }}）</span>
      </div>
      <div class="kv">
        <span class="k">提出者</span>
        <span class="v">{{ item.staged_by }}</span>
      </div>
      <div class="kv">
        <span class="k">参数</span>
        <span class="v">{{ JSON.stringify(item.params) }}</span>
      </div>
      <div v-if="item.before" class="snapshot">
        <div v-for="(val, key) in item.before" :key="key" class="kv">
          <span class="k">{{ key }}</span>
          <span class="v" :class="{ changed: isChanged(item, String(key)) }">{{ val }}</span>
        </div>
      </div>

      <div class="actions" style="margin-top: 12px">
        <input
          v-model="comments[item.id]"
          class="comment"
          :placeholder="placeholderFor(item.id)"
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
  params: Record<string, unknown>
  staged_by: string
  staged_at: string
  before: Record<string, unknown> | null
}

const items = ref<PendingItem[]>([])
const comments = ref<Record<number, string>>({})
const loading = ref(true)
const toast = ref('')
const toastIsError = ref(false)

function showToast(msg: string, isError = false) {
  toast.value = msg
  toastIsError.value = isError
  setTimeout(() => (toast.value = ''), 2500)
}

function placeholderFor(id: number) {
  return comments.value[id] ? '' : '审批意见（拒绝时必填）'
}

function isChanged(item: PendingItem, key: string): boolean {
  // v0.1：待审中心只展示 before 快照；变化字段高亮留 transform_log 接入后做
  return false
}

async function load() {
  loading.value = true
  try {
    items.value = await api.get('/api/staged/pending')
  } catch (e) {
    showToast(String(e), true)
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
