<template>
  <div>
    <h1 class="page-title">知识库</h1>
    <p class="page-desc">你的洞见、答案与各领域产出——全在本体层，这里是总入口</p>

    <!-- Tab 导航 -->
    <div class="tabs">
      <button v-for="t in tabs" :key="t.key" class="tab" :class="{ active: active === t.key }"
              @click="active = t.key; load()">{{ t.label }} <span class="count">{{ counts[t.key] || '' }}</span></button>
    </div>

    <!-- 洞见 -->
    <div v-if="active === 'insights'">
      <div v-if="loading" class="empty">加载中…</div>
      <div v-else-if="insights.length === 0" class="empty card">
        还没有洞见——去<a href="/ask" style="color:var(--primary)">深度问答</a>问几个问题并采纳答案，AI 会自动提炼
      </div>
      <div v-for="ins in insights" :key="ins.id" class="card">
        <div class="insight-takeaway">💡 {{ ins.properties.takeaway }}</div>
        <div v-if="ins.properties.context" class="kv"><span class="k">适用场景</span>
          <span class="v">{{ ins.properties.context }}</span></div>
        <div v-if="ins.properties.source_question" class="kv"><span class="k">来源问题</span>
          <span class="v">{{ ins.properties.source_question }}</span></div>
      </div>
    </div>

    <!-- 答案 -->
    <div v-if="active === 'answers'">
      <div v-if="loading" class="empty">加载中…</div>
      <div v-else-if="answers.length === 0" class="empty card">还没有答案历史</div>
      <div v-for="ans in answers" :key="ans.id" class="card">
        <div class="ans-q">Q: {{ ans.properties.question }}</div>
        <details>
          <summary class="ans-toggle">{{ ans.properties.adopted_by ? '✓ 已采纳' : '未采纳' }} · 查看答案</summary>
          <div class="ans-body">{{ ans.properties.content }}</div>
        </details>
      </div>
    </div>

    <!-- 域对象 -->
    <div v-if="active === 'objects'">
      <div v-if="loading" class="empty">加载中…</div>
      <div v-else class="card" style="padding:0">
        <table v-if="objects.length">
          <thead><tr><th>域</th><th>类型</th><th>标题</th><th>创建者</th><th>时间</th></tr></thead>
          <tbody>
            <tr v-for="o in objects" :key="o.id">
              <td>{{ o.object_type?.domain }}</td>
              <td>{{ o.object_type?.name }}</td>
              <td>{{ o.title || o.properties?.title || o.properties?.name || o.properties?.question?.slice(0,30) || `#${o.id}` }}</td>
              <td>{{ o.created_by || '—' }}</td>
              <td>{{ fmtTime(o.created_at) }}</td>
            </tr>
          </tbody>
        </table>
        <div v-else class="empty">暂无对象</div>
      </div>
    </div>

    <!-- forge 模板源码 -->
    <div v-if="active === 'forge'">
      <div v-if="loading" class="empty">加载中…</div>
      <div v-else-if="forgeTemplates.length === 0" class="empty card">
        还没有 forge 生成的模板——用 <code>yuanzhu forge "描述"</code> 或模板市场铸造框
      </div>
      <div v-for="tpl in forgeTemplates" :key="tpl.name" class="card">
        <div style="display:flex; justify-content:space-between; align-items:center">
          <b>{{ tpl.name }}</b>
          <span style="color:var(--muted); font-size:12px">{{ tpl.path }}</span>
        </div>
        <details style="margin-top:8px">
          <summary style="cursor:pointer; color:var(--muted); font-size:13px">查看 YAML 源码</summary>
          <div v-for="(content, fname) in tpl.files" :key="fname" style="margin-top:8px">
            <div class="file-name">{{ fname }}</div>
            <pre class="yaml-body">{{ content }}</pre>
          </div>
        </details>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { api } from '../api'

const tabs = [
  { key: 'insights', label: '💡 洞见' },
  { key: 'answers', label: '💬 答案' },
  { key: 'objects', label: '📦 全部对象' },
  { key: 'forge', label: '🔨 forge 模板' },
]
const active = ref('insights')
const loading = ref(false)
const counts = ref<Record<string, number>>({})

const insights = ref<any[]>([])
const answers = ref<any[]>([])
const objects = ref<any[]>([])
const forgeTemplates = ref<any[]>([])

async function load() {
  loading.value = true
  try {
    if (active.value === 'insights') {
      insights.value = await api.get('/api/objects?domain=metaflow&limit=100')
        .then((r: any[]) => r.filter(o => o.object_type?.name === 'Insight'))
      counts.value.insights = insights.value.length
    } else if (active.value === 'answers') {
      answers.value = await api.get('/api/objects?domain=metaflow&limit=100')
        .then((r: any[]) => r.filter(o => o.object_type?.name === 'Answer').reverse())
      counts.value.answers = answers.value.length
    } else if (active.value === 'objects') {
      objects.value = await api.get('/api/objects?limit=200')
      counts.value.objects = objects.value.length
    } else if (active.value === 'forge') {
      forgeTemplates.value = await api.get('/api/templates/forge-files')
    }
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

function fmtTime(t: string) {
  if (!t) return '—'
  return new Date(t).toLocaleString('zh-CN', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
}

onMounted(load)
</script>

<style scoped>
.tabs { display: flex; gap: 0; margin-bottom: 16px; border-bottom: 2px solid var(--border); }
.tab { padding: 10px 20px; border: none; background: none; cursor: pointer; font-size: 14px;
  color: var(--muted); border-bottom: 2px solid transparent; margin-bottom: -2px; }
.tab.active { color: var(--primary); border-bottom-color: var(--primary); font-weight: 500; }
.count { font-size: 12px; margin-left: 4px; }
.insight-takeaway { font-size: 14px; font-weight: 500; margin-bottom: 6px; }
.ans-q { font-weight: 500; margin-bottom: 6px; }
.ans-toggle { cursor: pointer; color: var(--primary); font-size: 13px; }
.ans-body { font-size: 13px; white-space: pre-wrap; line-height: 1.7; margin-top: 8px;
  background: var(--bg); padding: 12px; border-radius: 8px; word-break: break-all; }
.file-name { font-size: 12px; color: var(--muted); font-family: ui-monospace, Consolas, monospace; }
.yaml-body { font-size: 12px; background: var(--bg); padding: 10px 14px; border-radius: 8px;
  overflow-x: auto; white-space: pre-wrap; font-family: ui-monospace, Consolas, monospace; line-height: 1.5; }
</style>
