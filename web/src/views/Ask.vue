<template>
  <div>
    <h1 class="page-title">深度问答</h1>
    <p class="page-desc">你的问题自动走六步流水线：澄清 → 双视角并行作答 → 独立审查 → 综合裁决 → 等你采纳</p>

    <div class="card ask-card">
      <textarea v-model="question" class="comment" rows="3"
                placeholder="问一个你在纠结的真实决策，例如：我们该不该把客服外包出去？"
                :disabled="running"></textarea>
      <div class="actions" style="margin-top:10px; justify-content:flex-end">
        <span v-if="running" style="color:var(--muted); font-size:13px">
          {{ phase }}…（六步流水线约 2-4 分钟，可离开页面）
        </span>
        <button class="btn primary" :disabled="running || !question.trim()" @click="ask">
          {{ running ? '思考中' : '深度提问' }}
        </button>
      </div>
      <div v-if="error" class="error-box">{{ error }}</div>
    </div>

    <!-- 结果 -->
    <div v-if="result" class="card">
      <h3 style="margin-bottom:8px">综合裁决</h3>
      <div class="text-block-body">{{ result.final }}</div>
      <details style="margin-top:12px">
        <summary style="cursor:pointer; color:var(--muted)">看中间过程（澄清/视角A/视角B/审查）</summary>
        <div class="snapshot" style="margin-top:8px">
          <div v-for="(v, k) in result.details" :key="k" style="margin-bottom:12px">
            <b style="font-size:13px">{{ STAGE_NAMES[k] || k }}</b>
            <div class="text-block-body" style="margin-top:4px">{{ v }}</div>
          </div>
        </div>
      </details>
      <div class="actions" style="margin-top:14px; justify-content:flex-end">
        <button v-if="!adopted" class="btn primary" @click="adopt">采纳并存档</button>
        <span v-else style="color:var(--success)">✓ 已采纳</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { api } from '../api'

const question = ref('')
const running = ref(false)
const phase = ref('')
const error = ref('')
const result = ref<any>(null)
const adopted = ref(false)
const pendingExecId = ref<number | null>(null)

const STAGE_NAMES: Record<string, string> = {
  clarification: '① 澄清（多理解+关键未知）',
  ans_a: '② 视角A（务实推进者）',
  ans_b: '③ 视角B（质疑者·双盲并行）',
  audit: '④ 独立审查',
}

async function ask() {
  running.value = true
  error.value = ''
  result.value = null
  adopted.value = false
  const phases = ['澄清问题', '双视角并行作答', '独立审查', '综合裁决']
  let pi = 0
  phase.value = phases[0]
  const timer = setInterval(() => {
    pi = Math.min(pi + 1, phases.length - 1)
    phase.value = phases[pi]
  }, 45000)
  try {
    const r = await api.post('/api/workflows/run', {
      domain: 'metaflow', workflow: 'deep-answer',
      params: { question: question.value.trim() }, run_by: 'web-ask',
    })
    const steps = r.steps || {}
    result.value = {
      final: steps.verdict?.result || '（无输出）',
      details: {
        clarification: steps.clarification?.result,
        ans_a: steps['view-a']?.result,
        ans_b: steps['view-b']?.result,
        audit: steps.audit?.result,
      },
    }
    pendingExecId.value = steps.save?.exec_id ?? null
    if (steps.save?.status !== 'staged') {
      error.value = '答案未能进入待审区（请联系管理员）'
    }
  } catch (e) {
    error.value = String(e).replace('Error: ', '')
  } finally {
    clearInterval(timer)
    running.value = false
  }
}

async function adopt() {
  if (!pendingExecId.value) return
  try {
    await api.post(`/api/staged/${pendingExecId.value}/approve`, {
      reviewed_by: 'web-ask', review_comment: '采纳深度答案',
    })
    adopted.value = true
  } catch (e) {
    error.value = String(e).replace('Error: ', '')
  }
}
</script>

<style scoped>
.ask-card { border-left: 3px solid var(--primary); }
.error-box {
  background: #feecec; color: var(--danger);
  border-radius: 8px; padding: 10px 14px; font-size: 13px; margin-top: 10px;
  word-break: break-all;
}
.text-block-body {
  white-space: pre-wrap; font-size: 13px; line-height: 1.7; word-break: break-all;
}
.snapshot {
  background: var(--bg); border-radius: 8px; padding: 10px 14px;
}
</style>
