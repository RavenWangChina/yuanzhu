<template>
  <div>
    <h1 class="page-title">用量与审计</h1>
    <p class="page-desc">模型调用量 / token / 估费，以及最近调用明细</p>

    <div v-if="loading" class="empty">加载中…</div>
    <div v-else-if="loadError" class="empty card" style="color:var(--danger)">{{ loadError }}</div>
    <template v-else>
      <div v-if="data.summary.length === 0" class="empty card">近 {{ data.days }} 天暂无模型调用</div>

      <div v-for="s in data.summary" :key="s.model" class="card">
        <div style="display:flex; justify-content:space-between; align-items:center">
          <b>{{ s.model }}</b>
          <span style="color:var(--muted)">{{ s.calls }} 次调用</span>
        </div>
        <div class="kv" style="margin-top:6px">
          <span class="k">Token</span>
          <span class="v">输入 {{ s.prompt_tokens.toLocaleString() }} / 输出 {{ s.completion_tokens.toLocaleString() }}</span>
        </div>
        <div class="kv">
          <span class="k">估费</span>
          <span class="v">¥ {{ s.estimated_cost.toFixed(4) }}</span>
        </div>
      </div>

      <div v-if="data.recent.length" class="card" style="padding:0">
        <table>
          <thead>
            <tr><th>时间</th><th>模型</th><th>调用方</th><th>任务</th><th>Token</th></tr>
          </thead>
          <tbody>
            <tr v-for="r in data.recent" :key="r.id">
              <td>{{ new Date(r.created_at).toLocaleString('zh-CN') }}</td>
              <td>{{ r.model }}</td>
              <td>{{ r.caller }}</td>
              <td>{{ r.task_id ?? '—' }}</td>
              <td>{{ r.prompt_tokens }} / {{ r.completion_tokens }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { api } from '../api'

const data = ref<{ days: number; summary: any[]; recent: any[] }>({ days: 7, summary: [], recent: [] })
const loading = ref(true)

const loadError = ref('')
onMounted(async () => {
  try {
    data.value = await api.get('/api/usage?days=7')
  } catch (e) {
    loadError.value = `用量数据加载失败：${String(e).replace('Error: ', '')}`
  } finally {
    loading.value = false
  }
})
</script>
