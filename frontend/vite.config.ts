import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    // Proxy API/WebSocket calls to the FastAPI backend during dev, so
    // the browser only ever talks to one origin (localhost:5173) and
    // relative fetch('/api/...') / new WebSocket('/ws/live') calls
    // just work without hard-coding the backend's host:port in the
    // frontend source.
    proxy: {
      '/api': 'http://127.0.0.1:8000',
      '/health': 'http://127.0.0.1:8000',
      '/ws': {
        target: 'ws://127.0.0.1:8000',
        ws: true,
      },
    },
  },
})
