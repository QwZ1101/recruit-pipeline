import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// 后端只跑在本机 8000,库里是个人信息,别把 proxy 指到远端
export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    proxy: { '/api': { target: 'http://127.0.0.1:8000', changeOrigin: false } },
  },
})
