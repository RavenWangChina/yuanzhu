<template>
  <div>
    <h1 class="page-title">能力地图</h1>
    <p class="page-desc">元铸工坊的全部能力——域 / 对象 / 动作 / 工作流（实时从本体层读取）</p>

    <!-- 域选择 -->
    <div class="tabs">
      <button v-for="d in domains" :key="d" class="tab" :class="{ active: activeDomain === d }"
              @click="activeDomain = d; load()">{{ d }}</button>
    </div>

    <div v-if="loading" class="empty">加载中…</div>

    <template v-else>
      <!-- 对象类型 -->
      <h3>📦 对象类型</h3>
      <div v-if="objectTypes.length === 0" class="empty card">此域暂无对象类型</div>
      <div v-for="ot in objectTypes" :key="ot.id" class="card">
        <div style="display:flex; justify-content:space-between; align-items:center">
          <b style="font-size:15px">{{ ot.name }}</b>
          <span v-if="ot.exposed" class="badge published">MCP 已暴露</span>
        </div>
        <div v-if="ot.description" style="color:var(--muted); margin-top:4px">{{ ot.description }}</div>
        <div v-if="typeProps(ot)" class="kv" style="margin-top:8px">
          <span class="k">属性</span>
          <span class="v">{{ typeProps(ot) }}</span>
        </div>
      </div>

      <!-- 动作类型 -->
      <h3 style="margin-top:20px">⚡ 动作</h3>
      <div v-if="actionTypes.length === 0" class="empty card">此域暂无动作</div>
      <div v-for="at in actionTypes" :key="at.id" class="card">
        <div style="display:flex; justify-content:space-between; align-items:center">
          <b style="font-size:14px">{{ at.name }}</b>
          <span class="badge" :class="at.autonomy_level === 1 ? 'applied' : 'staged'">
            L{{ at.autonomy_level }} {{ at.autonomy_level === 1 ? '自动' : '人审' }}
          </span>
        </div>
        <div v-if="at.description_for_agent" style="color:var(--muted); margin-top:4px; font-size:13px">
          {{ at.description_for_agent }}
        </div>
      </div>

      <!-- 工作流 -->
      <h3 style="margin-top:20px">🔄 工作流</h3>
      <div v-if="workflows.length === 0" class="empty card">此域暂无工作流</div>
      <div v-for="wf in workflows" :key="wf.name" class="card">
        <b style="font-size:14px">{{ wf.name }}</b>
        <div v-if="wf.description" style="color:var(--muted); margin-top:4px; font-size:13px">{{ wf.description }}</div>
        <details style="margin-top:8px">
          <summary style="cursor:pointer; color:var(--muted); font-size:12px">步骤（{{ wf.steps?.length || 0 }}）</summary>
          <div v-for="(s, i) in wf.steps" :key="i" class="step-line">
            <span class="step-num">{{ i + 1 }}</span>
            <span>{{ s.name || s.id || s.action || s.type }}</span>
            <span class="step-type">{{ s.type }}</span>
          </div>
        </details>
      </div>

      <!-- 评测 -->
      <h3 style="margin-top:20px">🧪 评测用例</h3>
      <div v-if="evals.length === 0" class="empty card">此域暂无评测</div>
      <div class="card">
        <div v-for="(ev, i) in evals" :key="i" class="step-line">
          <span class="step-num">{{ i + 1 }}</span>
          <span>{{ ev.name }}</span>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { api } from '../api'

const domains = ref<string[]>([])
const activeDomain = ref('')
const loading = ref(false)
const objectTypes = ref<any[]>([])
const actionTypes = ref<any[]>([])
const workflows = ref<any[]>([])
const evals = ref<any[]>([])

function typeProps(ot: any): string {
  const schema = ot.schema_json || {}
  const props = schema.properties || {}
  return Object.keys(props).join(', ') || ''
}

async function load() {
  loading.value = true
  try {
    const d = activeDomain.value
    const [types, actions, templates] = await Promise.all([
      api.get(`/api/objects/types?domain=${d}`),
      api.get(`/api/actions/types?domain=${d}`),
      api.get('/api/templates'),
    ])
    objectTypes.value = types
    actionTypes.value = actions
    const tpl = templates.find((t: any) => t.domain === d)
    workflows.value = tpl?.workflows_json || []
    evals.value = tpl?.evals_json || []
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  // 获取所有域
  const templates = await api.get('/api/templates')
  const allDomains = new Set(templates.map((t: any) => t.domain))
  // 也从对象类型获取域
  try {
    const types = await api.get('/api/objects/types')
    types.forEach((t: any) => allDomains.add(t.domain))
  } catch {}
  domains.value = [...allDomains].sort()
  if (domains.value.length > 0) {
    activeDomain.value = domains.value[0]
    await load()
  }
})
</script>

<style scoped>
.tabs { display: flex; gap: 0; margin-bottom: 16px; border-bottom: 2px solid var(--border); flex-wrap: wrap; }
.tab { padding: 10px 20px; border: none; background: none; cursor: pointer; font-size: 14px;
  color: var(--muted); border-bottom: 2px solid transparent; margin-bottom: -2px; }
.tab.active { color: var(--primary); border-bottom-color: var(--primary); font-weight: 500; }
h3 { margin: 12px 0 8px; font-size: 15px; }
.badge { display: inline-block; padding: 2px 10px; border-radius: 999px; font-size: 12px; }
.badge.applied { background: #e8f7e8; color: var(--success); }
.badge.staged { background: #e8f0ff; color: var(--primary); }
.badge.published { background: #e8f7e8; color: var(--success); }
.step-line { display: flex; align-items: center; gap: 8px; padding: 6px 0; font-size: 13px; border-bottom: 1px dashed var(--border); }
.step-num { background: var(--primary); color: #fff; width: 20px; height: 20px; border-radius: 50%;
  display: flex; align-items: center; justify-content: center; font-size: 11px; flex-shrink: 0; }
.step-type { color: var(--muted); font-size: 11px; margin-left: auto; }
</style>
