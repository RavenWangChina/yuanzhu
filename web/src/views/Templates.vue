<template>
  <div>
    <h1 class="page-title">模板市场</h1>
    <p class="page-desc">已安装的工作流模板（四段式：对象模型 / 动作库 / 工作流 / 评测集）</p>

    <div v-if="loading" class="empty">加载中…</div>
    <div v-else-if="templates.length === 0" class="empty card">
      暂无模板。把模板目录注册到中控：<code>POST /api/templates/register</code>
    </div>

    <div v-for="t in templates" :key="t.id" class="card">
      <div style="display:flex; justify-content:space-between; align-items:center">
        <div>
          <b style="font-size:15px">{{ t.name }}</b>
          <span style="color:var(--muted)"> v{{ t.version }}</span>
          <span class="badge" :class="t.status" style="margin-left:8px">{{ statusText(t.status) }}</span>
        </div>
        <span style="color:var(--muted)">{{ t.domain }}</span>
      </div>
      <div v-if="t.manifest_json?.description" style="color:var(--muted); margin-top:6px">
        {{ t.manifest_json.description }}
      </div>
      <div class="kv" style="margin-top:8px">
        <span class="k">包含工作流</span>
        <span class="v">{{ (t.workflows_json || []).map((w: any) => w.name).join('、') || '—' }}</span>
      </div>
      <div class="kv">
        <span class="k">评测用例</span>
        <span class="v">{{ (t.evals_json || []).length }} 条</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { api } from '../api'

const templates = ref<any[]>([])
const loading = ref(true)

function statusText(s: string) {
  return { published: '已上架', draft: '草稿', staged: '待审' }[s] || s
}

onMounted(async () => {
  try {
    templates.value = await api.get('/api/templates')
  } finally {
    loading.value = false
  }
})
</script>
