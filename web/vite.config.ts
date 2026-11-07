import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'
import {loadEnv} from 'vite'

export default defineConfig(({mode})=>({
  plugins: [react()],
  server: { host: '127.0.0.1', port: 5173, proxy: { '/api': loadEnv(mode,'.','V8_').V8_API_PROXY_TARGET||'http://127.0.0.1:8765' } },
  test: { environment: 'jsdom', setupFiles: './src/test/setup.ts' },
}))
