import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  // Load .env from the project root (one level up from web/), so that
  // VITE_* variables defined in the repo-level .env are available to the
  // frontend. Without this, Vite only looks in web/ and misses the root
  // .env — causing VITE_API_URL to fall back to its default (port 8000
  // instead of the LMS backend on port 8001).
  envDir: '..',
  plugins: [vue()],
  server: {
    host: '0.0.0.0',
    port: 5173,
    strictPort: false,
  },
  build: {
    outDir: 'dist',
    sourcemap: false,
  },
})
