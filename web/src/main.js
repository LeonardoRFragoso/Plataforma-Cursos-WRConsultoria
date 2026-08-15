import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'
import './style.css'
import { useTenantStore } from './stores/tenant'

const app = createApp(App)

app.use(createPinia())

const tenantStore = useTenantStore()
const slug = window.location.hostname.split('.')[0] || 'wr'
tenantStore.loadBranding(slug).then(() => tenantStore.applyColors())

app.use(router)

app.mount('#app')
