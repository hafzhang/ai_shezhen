import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'

export default defineConfig({
  plugins: [
    vue({
      template: {
        compilerOptions: {
          isCustomElement: (tag) => tag.startsWith('u-')
        }
      }
    })
  ],
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
    },
    rollupOptions: {
      onwarn(warning, warn) {
        // Ignore warnings about uview-plus components
        if (warning.code === 'CIRCULAR_DEPENDENCY' ||
            warning.message?.includes('uview-plus')) {
          return
        }
        warn(warning)
      },
      output: {
        // Suppress the "Identifier 'currentIndex' has already been declared" warning
        manualChunks: {
          'uview-plus': ['uview-plus']
        }
      }
    }
  }
})
