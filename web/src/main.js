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
tenantStore.loadBranding(slug).then(() => {
  tenantStore.applyColors()
  const name = tenantStore.name || 'Plataforma de Cursos'
  document.title = name
  const meta = document.querySelector('meta[name="description"]')
  if (meta) meta.content = `Cursos e certificações - ${name}`
})

app.use(router)

app.mount('#app')
