import { createRouter, createWebHistory } from 'vue-router'
import Nodes from './views/Nodes.vue'
import Templates from './views/Templates.vue'
import Staged from './views/Staged.vue'
import Usage from './views/Usage.vue'
import Knowledge from './views/Knowledge.vue'
import Chat from './views/Chat.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/ask' },
    { path: '/ask', component: Chat },
    { path: '/nodes', component: Nodes },
    { path: '/templates', component: Templates },
    { path: '/staged', component: Staged },
    { path: '/usage', component: Usage },
    { path: '/knowledge', component: Knowledge },
  ],
})

export default router
