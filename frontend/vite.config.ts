import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// In dev, API calls go to /api/... and are proxied to the FastAPI backend, so no
// CORS configuration is needed in the browser. Override the target with
// VITE_PROXY_TARGET (used by docker-compose, where the backend host is "backend").
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    strictPort: true,
    proxy: {
      '/api': {
        target: process.env.VITE_PROXY_TARGET ?? 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
})
