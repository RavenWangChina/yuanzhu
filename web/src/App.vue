<template>
  <div class="layout">
    <nav class="sidebar">
      <div class="brand">元铸工坊</div>
      <router-link class="nav-item" to="/ask">深度问答</router-link>
      <router-link class="nav-item" to="/staged">待审中心</router-link>
      <router-link class="nav-item" to="/templates">模板市场</router-link>
      <router-link class="nav-item" to="/nodes">节点拓扑</router-link>
      <router-link class="nav-item" to="/knowledge">知识库</router-link>
      <router-link class="nav-item" to="/usage">用量与审计</router-link>
    </nav>
    <main class="main">
      <router-view />
    </main>
  </div>
</template>

<script setup lang="ts">
// 导航激活态样式见 style.css（.nav-item.router-link-active）
</script>

