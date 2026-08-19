import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'
import './style.css'
import { useTenantStore } from './stores/tenant'
import { TENANT_SLUG } from './utils/tenantSlug'

const app = createApp(App)

app.use(createPinia())

const tenantStore = useTenantStore()
tenantStore.loadBranding(TENANT_SLUG).then(() => {
  tenantStore.applyColors()
  const name = tenantStore.name || 'Plataforma de Cursos'
  document.title = name
  const meta = document.querySelector('meta[name="description"]')
  if (meta) meta.content = `Cursos e certificações - ${name}`
  tenantStore.applyFavicon()
})

app.use(router)

app.mount('#app')
