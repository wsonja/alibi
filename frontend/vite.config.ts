import { fileURLToPath, URL } from 'node:url'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { defineConfig, type UserConfig } from 'vite'

// Murder Mystery Mayhem — frontend build config.
// The API base URL is read at runtime from VITE_API_URL (default http://localhost:8000), see src/api/client.ts.
//
// Vitest reads the `test` block below. Its types come from `vitest/config`, which (in this install) is typed
// against Vitest's own nested Vite 7 copy and clashes with the Vite 8 plugin types, so the block is typed
// structurally here instead of importing `vitest/config`.
interface VitestBlock {
  test?: {
    environment?: 'node' | 'jsdom' | 'happy-dom'
    include?: string[]
    css?: boolean
    globals?: boolean
  }
}

const config: UserConfig & VitestBlock = {
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    host: true,
    port: 5173,
    strictPort: false,
  },
  preview: {
    port: 5173,
  },
  build: {
    sourcemap: false,
    chunkSizeWarningLimit: 900,
  },
  test: {
    environment: 'node',
    include: ['src/**/*.{test,spec}.{ts,tsx}'],
    css: false,
  },
}

export default defineConfig(config)
