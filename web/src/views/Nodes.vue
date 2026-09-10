<template>
  <div>
    <h1 class="page-title">节点拓扑</h1>
    <p class="page-desc">已注册的执行节点（单机模式下显示内置执行器）</p>

    <div v-if="loading" class="empty">加载中…</div>
    <div v-else-if="loadError" class="empty card" style="color:var(--danger)">{{ loadError }}</div>
    <div v-else-if="nodes.length === 0" class="empty card">暂无节点注册</div>

    <div class="card" style="padding:0">
      <table>
        <thead>
          <tr>
            <th>节点</th><th>状态</th><th>能力</th><th>资源水位</th><th>最近心跳</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="n in nodes" :key="n.id">
            <td><b>{{ n.name }}</b></td>
            <td><span class="badge" :class="n.status">{{ statusText(n.status) }}</span></td>
            <td>{{ capabilityText(n.capabilities) }}</td>
            <td>{{ usageText(n.resource_usage) }}</td>
            <td>{{ heartbeatText(n.last_heartbeat) }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { api } from '../api'

const nodes = ref<any[]>([])
const loading = ref(true)

function statusText(s: string) {
  return { online: '在线', busy: '忙碌', offline: '离线' }[s] || s
}
function capabilityText(caps: Record<string, unknown> | null) {
  if (!caps) return '—'
  const parts: string[] = []
  if (caps.os) parts.push(String(caps.os))
  if (caps.dsh) parts.push('DSH')
  if (caps.gpu) parts.push('GPU')
  return parts.join(' / ') || '—'
}
function usageText(u: Record<string, number> | null) {
  if (!u) return '—'
  const parts: string[] = []
  if (u.cpu != null) parts.push(`CPU ${u.cpu.toFixed(0)}%`)
  if (u.memory != null) parts.push(`内存 ${u.memory.toFixed(0)}%`)
  return parts.join(' / ') || '—'
}
function heartbeatText(t: string | null) {
  if (!t) return '从未'
  const diff = (Date.now() - new Date(t).getTime()) / 1000
  if (diff < 90) return `${Math.floor(diff)} 秒前`
  if (diff < 3600) return `${Math.floor(diff / 60)} 分钟前`
  return new Date(t).toLocaleString('zh-CN')
}

const loadError = ref('')
onMounted(async () => {
  try {
    nodes.value = await api.get('/api/nodes')
  } catch (e) {
    loadError.value = `节点列表加载失败：${String(e).replace('Error: ', '')}`
  } finally {
    loading.value = false
  }
})
</script>
