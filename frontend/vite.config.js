import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    // In local dev the backend runs on :8000; in Docker nginx handles /api
    proxy: {
      '/api': 'http://localhost:8000',
    },
  },
})
