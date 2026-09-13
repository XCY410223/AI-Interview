import { fileURLToPath, URL } from 'node:url'

import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vitest/config'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    proxy: {
      '/api': {
        // base 模式只发布 nginx 80 端口（nginx 反向代理到 app:8006）；
        // 若改用开发覆盖层 `-f docker-compose.dev.yml`（发布 8006），把这里改成 http://localhost:8006
        target: 'http://localhost:80',
        changeOrigin: true,
      },
    },
  },
  test: {
    environment: 'jsdom',
    include: ['src/**/*.{test,spec}.ts'],
    setupFiles: ['./src/test-setup.ts'],
  },
})
