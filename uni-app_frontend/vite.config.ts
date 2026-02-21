import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src')
    }
  },
  css: {
    preprocessorOptions: {
      scss: {
        additionalData: `@import "@/uni_modules/uview-plus/theme.scss";@import "uni.scss";`
      }
    }
  },
  optimizeDeps: {
    exclude: ['uview-plus'],
    include: []
  },
  server: {
    port: 3000,
    host: '0.0.0.0',
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        rewrite: (path) => path
      }
    }
  },
  build: {
    target: 'es6',
    outDir: 'dist',
    assetsDir: 'static',
    sourcemap: false,
    commonjsOptions: {
      transformMixedEsModules: true
    }
  }
})
