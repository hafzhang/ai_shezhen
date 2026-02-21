<template>
  <div class="app">
    <router-view />
  </div>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import { useUserStore } from '@/store'
import { initializeRouteGuard } from '@/utils/routeGuard'

onMounted(async () => {
  console.log('App Mounted')

  // Initialize authentication state from storage (H5 auto-login)
  const userStore = useUserStore()
  await userStore.initializeAuth()

  // Initialize route guards after auth state is ready
  // This will check if the current page requires authentication
  initializeRouteGuard()
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
}
</style>
