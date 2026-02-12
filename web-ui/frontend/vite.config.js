import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'


export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://localhost:8022',
        changeOrigin: true,
      },
      '/ws': {
        target: 'ws://localhost:8022',
        ws: true,
      },
    },
  },
  build: {
    outDir: 'dist', // expliciet relatieve output dir voor Vercel
  },
})
