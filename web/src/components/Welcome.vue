<template>
  <div v-if="visible" class="welcome-overlay">
    <div class="welcome-card">
      <h2>👋 欢迎来到元铸工坊</h2>
      <p class="slogan">AI 提议，人拍板——把日常工作铸成可治理的 AI 工作流资产</p>

      <div class="steps">
        <div class="step" @click="go('/staged')">
          <span class="step-num">①</span>
          <div>
            <b>审一条 AI 的提议</b>
            <p>去待审中心看 AI 提交了什么，点「批准」让它生效</p>
          </div>
        </div>
        <div class="step" @click="go('/ask')">
          <span class="step-num">②</span>
          <div>
            <b>问它一个工作问题</b>
            <p>例如「新同事入职要准备什么」——答案会沉淀进知识库</p>
          </div>
        </div>
        <div class="step" @click="go('/templates')">
          <span class="step-num">③</span>
          <div>
            <b>铸一个你的工作流</b>
            <p>在模板市场输入一句日常工作描述，看 AI 铸成模板</p>
          </div>
        </div>
      </div>

      <div class="demo-hint">
        库里还没有数据？终端运行
        <code>yuanzhu-demo</code>
        一键灌入演示数据体验
      </div>

      <button class="btn primary" @click="dismiss">开始使用</button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../api'

const visible = ref(false)
const router = useRouter()

function dismiss() {
  visible.value = false
  localStorage.setItem('yuanzhu-welcomed', '1')
}

function go(path: string) {
  dismiss()
  router.push(path)
}

onMounted(async () => {
  if (localStorage.getItem('yuanzhu-welcomed')) return
  try {
    const r = await api.get('/api/first-run')
    if (r.first_run) visible.value = true
  } catch { /* 检测失败不打扰 */ }
})
</script>

<style scoped>
.welcome-overlay {
  position: fixed; inset: 0; background: rgba(15, 17, 24, 0.72);
  display: flex; align-items: center; justify-content: center; z-index: 999;
}
.welcome-card {
  background: var(--bg-card, #fff); border-radius: 14px; padding: 32px 36px;
  width: min(520px, 92vw); box-shadow: 0 24px 64px rgba(0, 0, 0, 0.35);
}
h2 { margin: 0 0 6px; font-size: 22px; }
.slogan { color: var(--muted, #888); font-size: 14px; margin: 0 0 20px; }
.steps { display: flex; flex-direction: column; gap: 10px; margin-bottom: 16px; }
.step {
  display: flex; gap: 12px; align-items: flex-start; padding: 12px 14px;
  border: 1px solid var(--border, #e5e5e5); border-radius: 10px; cursor: pointer;
  transition: border-color 0.15s;
}
.step:hover { border-color: var(--primary, #4a7dd8); }
.step-num { font-size: 18px; }
.step b { font-size: 14px; display: block; }
.step p { margin: 2px 0 0; font-size: 13px; color: var(--muted, #999); }
.demo-hint {
  font-size: 12.5px; color: var(--muted, #999); margin-bottom: 18px;
  padding: 10px 12px; background: var(--bg-inset, #f7f7f8); border-radius: 8px;
}
.demo-hint code { background: none; padding: 1px 4px; color: var(--primary, #4a7dd8); }
.welcome-card .btn { width: 100%; }
</style>
