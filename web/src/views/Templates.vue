<template>
  <div>
    <h1 class="page-title">模板市场</h1>
    <p class="page-desc">已安装的工作流模板——点「使用」即可运行，产出进入待审中心等你确认</p>

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

      <!-- 工作流「使用」入口（H2：非技术者从这里触发任务） -->
      <div v-if="(t.workflows_json || []).length && t.status === 'published'" style="margin-top:10px">
        <div v-for="w in t.workflows_json" :key="w.name"
             style="display:flex; justify-content:space-between; align-items:center; padding:8px 0;
                    border-top:1px dashed var(--border)">
          <div>
            <b>{{ w.name }}</b>
            <span style="color:var(--muted); margin-left:8px">{{ w.description }}</span>
          </div>
          <button class="btn primary" @click="openRun(t, w)">使用</button>
        </div>
      </div>
      <div class="kv" style="margin-top:8px">
        <span class="k">评测用例</span>
        <span class="v">{{ (t.evals_json || []).length }} 条</span>
      </div>
    </div>

    <!-- 运行弹窗 -->
    <div v-if="runDialog.visible" class="modal-mask" @click.self="runDialog.visible = false">
      <div class="modal card" style="margin:auto; width:460px">
        <h3 style="margin-bottom:4px">使用「{{ runDialog.workflow.name }}」</h3>
        <p style="color:var(--muted); margin-bottom:14px">{{ runDialog.workflow.description }}</p>

        <div v-for="p in runDialog.schema" :key="p.name" style="margin-bottom:12px">
          <label style="display:block; margin-bottom:4px">
            {{ p.label }}<span v-if="p.required" style="color:var(--danger)">*</span>
          </label>
          <input v-if="p.type !== 'text'" v-model="runDialog.values[p.name]" class="comment"
                 :placeholder="p.placeholder" />
          <textarea v-else v-model="runDialog.values[p.name]" class="comment" rows="3"
                    :placeholder="p.placeholder" />
        </div>

        <div v-if="runError" class="error-box">{{ runError }}</div>

        <div class="actions" style="justify-content:flex-end">
          <button class="btn" @click="runDialog.visible = false">取消</button>
          <button class="btn primary" :disabled="running" @click="submitRun">
            {{ running ? '运行中…' : '开始运行' }}
          </button>
        </div>
      </div>
    </div>

    <div v-if="toast" class="toast" :class="{ error: toastIsError }">{{ toast }}</div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../api'

const router = useRouter()
const templates = ref<any[]>([])
const loading = ref(true)
const running = ref(false)
const toast = ref('')
const toastIsError = ref(false)

const runError = ref('')

const runDialog = ref({
  visible: false,
  domain: '',
  workflow: {} as any,
  schema: [] as any[],
  values: {} as Record<string, string>,
})

function statusText(s: string) {
  return { published: '已上架', draft: '草稿', staged: '待审' }[s] || s
}

function showToast(msg: string, isError = false) {
  toast.value = msg
  toastIsError.value = isError
  setTimeout(() => (toast.value = ''), 3200)
}

function openRun(tpl: any, wf: any) {
  runError.value = ''
  runDialog.value = {
    visible: true,
    domain: tpl.domain,
    workflow: wf,
    schema: wf.params_schema || [],
    values: {},
  }
}

async function submitRun() {
  const { domain, workflow, schema, values } = runDialog.value
  for (const p of schema) {
    if (p.required && !values[p.name]?.trim()) {
      showToast(`请填写「${p.label}」`, true)
      return
    }
  }
  running.value = true
  try {
    const result = await api.post('/api/workflows/run', {
      domain, workflow: workflow.name, params: values, run_by: 'web-user',
    })
    // 统计进入待审的动作数
    let staged = 0
    for (const key of Object.keys(result.steps || {})) {
      const s = result.steps[key]
      if (s.status === 'staged') staged += 1
      if (s.staged_count) staged += s.staged_count
    }
    runDialog.value.visible = false
    if (staged > 0) {
      showToast(`运行完成：${staged} 项产出等待你审批`)
      setTimeout(() => router.push('/staged'), 1200)
    } else {
      showToast('运行完成（无需审批的产出已直接生效）')
    }
  } catch (e) {
    runError.value = String(e).replace('Error: ', '')  // 弹窗内常驻（H2：出错必可见）
  } finally {
    running.value = false
  }
}

onMounted(async () => {
  try {
    templates.value = await api.get('/api/templates')
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.modal-mask {
  position: fixed; inset: 0; background: rgba(0,0,0,.35);
  display: flex; z-index: 50;
}
.modal { box-shadow: 0 8px 30px rgba(0,0,0,.15); }
.error-box {
  background: #feecec; color: var(--danger);
  border-radius: 8px; padding: 10px 14px;
  font-size: 13px; margin-bottom: 12px; word-break: break-all;
}
</style>
