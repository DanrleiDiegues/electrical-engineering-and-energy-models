import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { viteSingleFile } from 'vite-plugin-singlefile'

// Em desenvolvimento, as chamadas a /api são repassadas à API Python (porta 8000), sem problemas de CORS.
// `npm run build:arquivo` gera um único HTML que abre direto do disco (use ?demo para dados de exemplo).
export default defineConfig(({ mode }) => ({
  plugins: [react(), ...(mode === 'arquivo' ? [viteSingleFile()] : [])],
  base: mode === 'arquivo' ? './' : '/',
  server: {
    port: 5173,
    proxy: { '/api': { target: 'http://127.0.0.1:8000', rewrite: p => p.replace(/^\/api/, '') } },
  },
}))
