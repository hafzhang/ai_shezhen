<template>
  <div id="app" class="app">
    <router-view />
  </div>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import { useUserStore } from '@/store'
import { useDarkMode } from '@/composables'

// Initialize dark mode
useDarkMode()

onMounted(async () => {
  console.log('App Mounted')

  // Initialize authentication state from storage (H5 auto-login)
  const userStore = useUserStore()
  await userStore.initializeAuth()
})
</script>

<style lang="scss">
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

html, body {
  height: 100%;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Hiragino Sans GB',
    'Microsoft YaHei', 'Helvetica Neue', Helvetica, Arial, sans-serif;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

#app {
  height: 100%;
}

.app {
  min-height: 100vh;
  background-color: #f5f5f5;
  font-size: 16px;
  line-height: 1.5;
  color: #333;
  transition: background-color 0.3s ease, color 0.3s ease;
}

/* Dark mode styles */
:global(.dark-mode) .app {
  background-color: #1a1a1a;
  color: #e0e0e0;
}

:global(.light-mode) .app {
  background-color: #f5f5f5;
  color: #333;
}
</style>
