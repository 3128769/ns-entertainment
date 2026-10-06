import { fileURLToPath, URL } from 'node:url'
import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vitest/config'

// During development the API is the real backend (see backend/dev/README.md).
const backend = process.env.NS_BACKEND ?? 'http://127.0.0.1:8090'

export default defineConfig({
  plugins: [vue()],
  resolve: { alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) } },
  server: { port: 5173, proxy: { '/api': backend, '/healthz': backend } },
  build: { target: 'es2022', sourcemap: false, chunkSizeWarningLimit: 600 },
  test: { environment: 'jsdom', include: ['src/**/*.test.ts'] },
})
