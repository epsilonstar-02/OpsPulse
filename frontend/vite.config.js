import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 8080,
    proxy: {
      // Proxy API requests to the backend
      '/api': {
        target: 'http://34.171.226.157:8001',
        changeOrigin: true,
        secure: false,
      },
      // Note: WebSocket connections go directly to backend (ws://localhost:8001)
      // to avoid Vite proxy issues with high-throughput WebSocket streams
    },
  },
})
