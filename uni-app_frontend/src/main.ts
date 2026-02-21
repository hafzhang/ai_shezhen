import { createApp } from 'vue'
import { createPinia } from 'pinia'
import piniaPluginPersistedstate from 'pinia-plugin-persistedstate'
import uviewPlus from 'uview-plus'
import App from './App.vue'
import router from './router'
import i18n from './locales'

// Create Vue app
const app = createApp(App)

// Create Pinia store
const pinia = createPinia()
pinia.use(piniaPluginPersistedstate)

app.use(pinia)
app.use(router)
app.use(uviewPlus)
app.use(i18n)

app.mount('#app')
