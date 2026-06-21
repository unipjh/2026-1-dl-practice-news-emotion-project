import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      '/headlines': 'http://localhost:8000',
      '/crawler': 'http://localhost:8000',
      '/predict': 'http://localhost:8000',
      '/health': 'http://localhost:8000',
    },
  },
})
