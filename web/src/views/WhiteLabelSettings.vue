<template>
  <div class="min-h-screen bg-gray-50">
    <AppNavbar />
    <div class="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <h1 class="text-2xl font-bold text-secondary-900 mb-6">White Label — Configurações</h1>

      <div v-if="error" class="mb-4 rounded-md bg-red-50 p-4 text-sm text-red-700">
        {{ error }}
      </div>
      <div v-if="success" class="mb-4 rounded-md bg-green-50 p-4 text-sm text-green-700">
        Branding atualizado com sucesso!
      </div>

      <form @submit.prevent="handleSave" class="space-y-6 bg-white p-6 rounded-lg shadow-md border border-gray-200">
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">Nome da Plataforma</label>
          <input
            v-model="form.name"
            type="text"
            class="w-full rounded-md border-gray-300 border px-3 py-2 focus:ring-primary-500 focus:border-primary-500"
            placeholder="Ex: Alfa Academy"
          />
        </div>

        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">URL do Logo</label>
          <input
            v-model="form.logo_url"
            type="url"
            class="w-full rounded-md border-gray-300 border px-3 py-2"
            placeholder="https://..."
          />
        </div>

        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">URL do Logo (branco)</label>
          <input
            v-model="form.logo_white_url"
            type="url"
            class="w-full rounded-md border-gray-300 border px-3 py-2"
            placeholder="https://..."
          />
        </div>

        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">URL do Favicon</label>
          <input
            v-model="form.favicon_url"
            type="url"
            class="w-full rounded-md border-gray-300 border px-3 py-2"
            placeholder="https://..."
          />
        </div>

        <div class="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">Cor Primária</label>
            <div class="flex items-center gap-2">
              <input
                v-model="form.primary_color"
                type="color"
                class="h-10 w-14 rounded border border-gray-300"
              />
              <input
                v-model="form.primary_color"
                type="text"
                class="flex-1 rounded-md border-gray-300 border px-3 py-2 text-sm"
                placeholder="#0056b3"
              />
            </div>
          </div>
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">Cor Secundária</label>
            <div class="flex items-center gap-2">
              <input
                v-model="form.secondary_color"
                type="color"
                class="h-10 w-14 rounded border border-gray-300"
              />
              <input
                v-model="form.secondary_color"
                type="text"
                class="flex-1 rounded-md border-gray-300 border px-3 py-2 text-sm"
                placeholder="#1a1a1a"
              />
            </div>
          </div>
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">Cor de Destaque</label>
            <div class="flex items-center gap-2">
              <input
                v-model="form.accent_color"
                type="color"
                class="h-10 w-14 rounded border border-gray-300"
              />
              <input
                v-model="form.accent_color"
                type="text"
                class="flex-1 rounded-md border-gray-300 border px-3 py-2 text-sm"
                placeholder="#ff6b35"
              />
            </div>
          </div>
        </div>

        <div class="flex justify-end">
          <button
            type="submit"
            :disabled="saving"
            class="bg-primary-600 text-white px-6 py-2 rounded-md hover:bg-primary-700 font-semibold text-sm transition-colors disabled:opacity-50"
          >
            {{ saving ? 'Salvando...' : 'Salvar Branding' }}
          </button>
        </div>
      </form>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import AppNavbar from '../components/AppNavbar.vue'
import { useTenantStore } from '../stores/tenant'
import { updateTenantBranding } from '../api/tenant'
import { TENANT_SLUG } from '../utils/tenantSlug'

const tenantStore = useTenantStore()
const saving = ref(false)
const success = ref(false)
const error = ref('')

const form = ref({
  name: '',
  logo_url: '',
  logo_white_url: '',
  favicon_url: '',
  primary_color: '',
  secondary_color: '',
  accent_color: '',
})

onMounted(() => {
  form.value = {
    name: tenantStore.name || '',
    logo_url: tenantStore.logo_url || '',
    logo_white_url: tenantStore.logo_white_url || '',
    favicon_url: tenantStore.favicon_url || '',
    primary_color: tenantStore.primary_color || '',
    secondary_color: tenantStore.secondary_color || '',
    accent_color: tenantStore.accent_color || '',
  }
})

async function handleSave() {
  saving.value = true
  success.value = false
  error.value = ''
  try {
    const payload = {}
    for (const [key, val] of Object.entries(form.value)) {
      if (val && val.trim()) payload[key] = val.trim()
    }
    await updateTenantBranding(payload)
    await tenantStore.refreshBranding(TENANT_SLUG)
    success.value = true
  } catch (err) {
    error.value = err.response?.data?.detail || 'Erro ao salvar branding'
  } finally {
    saving.value = false
  }
}
</script>
