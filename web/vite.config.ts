import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  // dev 代理到本地中控
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://127.0.0.1:8600',
      '/mcp': 'http://127.0.0.1:8600',
    },
  },
  // 构建产物给 FastAPI 托管
  build: {
    outDir: '../server/static',
    emptyOutDir: true,
  },
})
