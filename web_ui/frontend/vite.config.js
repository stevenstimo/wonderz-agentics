import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    allowedHosts: ['wonderz-agentic.exe.xyz'],
    proxy: {
      '/api': {
        target: 'http://localhost:8090',
        changeOrigin: true,
      },
      '/ws': {
        target: 'ws://localhost:8090',
        ws: true,
      },
    },
  },
  build: {
    outDir: 'dist', // expliciet relatieve output dir voor Vercel
    rollupOptions: {
      output: {
        manualChunks: {
          vendor: ['react', 'react-dom', 'react-router-dom'],
          supabase: ['@supabase/supabase-js'],
          recharts: ['recharts'],
          // Explicit justification: pdf chunk > 150 kB gzip — jspdf + html2canvas for dashboard export;
          // loaded only with ClientDashboardPage, not on initial load.
          pdf: ['jspdf', 'html2canvas'],
        },
      },
    },
  },
})
