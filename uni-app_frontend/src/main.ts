import { createApp } from 'vue'
import { createPinia } from 'pinia'
import piniaPluginPersistedstate from 'pinia-plugin-persistedstate'
import uviewPlus from 'uview-plus'
import App from './App.vue'
import router from './router'

// Create Vue app
const app = createApp(App)

// Create Pinia store
const pinia = createPinia()
pinia.use(piniaPluginPersistedstate)

app.use(pinia)
app.use(router)
app.use(uviewPlus)

app.mount('#app')
