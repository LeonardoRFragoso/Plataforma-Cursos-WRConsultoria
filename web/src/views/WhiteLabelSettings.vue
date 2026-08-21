<template>
  <div>
    <div class="max-w-3xl mx-auto">
      <AppPageHeader title="White Label — Configurações" description="Personalize a identidade da plataforma." />

      <AppAlert v-if="error" type="error" closable @close="error = ''">{{ error }}</AppAlert>
      <AppAlert v-if="success" type="success" closable @close="success = false">Branding atualizado com sucesso!</AppAlert>

      <form @submit.prevent="handleSave" class="space-y-6 bg-white p-6 rounded-lg shadow-md border border-gray-200">
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">Nome da Plataforma</label>
          <input
            v-model="form.name"
            type="text"
            class="w-full rounded-md border-gray-300 border px-3 py-2 focus:ring-primary-500 focus:border-primary-500"
            placeholder="Ex: Alfa Academy"
            data-testid="wl-name-input"
          />
          <p class="text-xs text-gray-500 mt-1">Exibido no cabeçalho, rodapé e título da página.</p>
        </div>

        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">URL do Logo</label>
          <input
            v-model="form.logo_url"
            type="url"
            class="w-full rounded-md border-gray-300 border px-3 py-2"
            placeholder="https://..."
            data-testid="wl-logo-input"
          />
          <p class="text-xs text-gray-500 mt-1">URL da imagem do logo (recomendado: SVG ou PNG transparente, altura máx. 48px).</p>
          <div v-if="form.logo_url" class="mt-2 p-3 bg-gray-50 rounded-md">
            <img :src="form.logo_url" alt="Preview do logo" class="h-12 w-auto" />
            <p class="text-xs text-gray-400 mt-1">Pré-visualização</p>
          </div>
        </div>

        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">URL do Logo (branco)</label>
          <input
            v-model="form.logo_white_url"
            type="url"
            class="w-full rounded-md border-gray-300 border px-3 py-2"
            placeholder="https://..."
            data-testid="wl-logo-white-input"
          />
          <p class="text-xs text-gray-500 mt-1">Versão branca do logo para fundos escuros (hero, rodapé).</p>
        </div>

        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">URL do Favicon</label>
          <input
            v-model="form.favicon_url"
            type="url"
            class="w-full rounded-md border-gray-300 border px-3 py-2"
            placeholder="https://..."
            data-testid="wl-favicon-input"
          />
          <p class="text-xs text-gray-500 mt-1">Ícone exibido na aba do navegador (recomendado: 32x32px ICO ou PNG).</p>
        </div>

        <div class="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">Cor Primária</label>
            <div class="flex items-center gap-2">
              <input
                v-model="form.primary_color"
                type="color"
                class="h-10 w-14 rounded border border-gray-300"
                data-testid="wl-primary-color"
              />
              <input
                v-model="form.primary_color"
                type="text"
                class="flex-1 rounded-md border-gray-300 border px-3 py-2 text-sm"
                placeholder="#0056b3"
              />
            </div>
            <p class="text-xs text-gray-500 mt-1">Cor principal de botões e links.</p>
          </div>
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">Cor Secundária</label>
            <div class="flex items-center gap-2">
              <input
                v-model="form.secondary_color"
                type="color"
                class="h-10 w-14 rounded border border-gray-300"
                data-testid="wl-secondary-color"
              />
              <input
                v-model="form.secondary_color"
                type="text"
                class="flex-1 rounded-md border-gray-300 border px-3 py-2 text-sm"
                placeholder="#1a1a1a"
              />
            </div>
            <p class="text-xs text-gray-500 mt-1">Cor de títulos e textos de destaque.</p>
          </div>
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">Cor de Destaque</label>
            <div class="flex items-center gap-2">
              <input
                v-model="form.accent_color"
                type="color"
                class="h-10 w-14 rounded border border-gray-300"
                data-testid="wl-accent-color"
              />
              <input
                v-model="form.accent_color"
                type="text"
                class="flex-1 rounded-md border-gray-300 border px-3 py-2 text-sm"
                placeholder="#ff6b35"
              />
            </div>
            <p class="text-xs text-gray-500 mt-1">Cor de elementos de destaque e notificações.</p>
          </div>
        </div>

        <div class="flex justify-end">
          <button
            type="submit"
            :disabled="saving"
            class="bg-primary-600 text-white px-6 py-2 rounded-md hover:bg-primary-700 font-semibold text-sm transition-colors disabled:opacity-50"
            data-testid="wl-save-btn"
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
import AppPageHeader from '../components/AppPageHeader.vue'
import AppAlert from '../components/AppAlert.vue'
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

  // Basic validation
  if (form.value.name && form.value.name.trim().length > 100) {
    error.value = 'O nome da plataforma deve ter no máximo 100 caracteres.'
    saving.value = false
    return
  }

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
