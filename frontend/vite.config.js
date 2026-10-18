import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

const apiTarget = process.env.RIVERGUARD_API_URL || 'http://127.0.0.1:8010'

// Dev server proxies /api to the Django backend so the frontend can call it
// without CORS pain during development.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': apiTarget,
    },
  },
})
