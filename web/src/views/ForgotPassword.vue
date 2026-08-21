<template>
  <div class="min-h-screen bg-gray-50 flex flex-col">
    <header class="bg-primary-600 text-white py-6">
      <div class="max-w-3xl mx-auto px-4 text-center">
        <h1 class="text-2xl font-bold">Recuperar senha</h1>
        <p class="text-white/80 text-sm mt-1">Informe seu e-mail para receber as instruções.</p>
      </div>
    </header>

    <main class="flex-1 flex items-center justify-center p-6">
      <div class="w-full max-w-md bg-white rounded-lg shadow-lg p-8">
        <!-- Initial form -->
        <form v-if="!submitted" class="space-y-4" @submit.prevent="handleSubmit">
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">E-mail</label>
            <input
              v-model="email"
              type="email"
              required
              placeholder="seu@email.com"
              class="w-full p-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-600"
              data-testid="forgot-email-input"
            />
          </div>

          <AppAlert v-if="error" type="error">{{ error }}</AppAlert>

          <button
            type="submit"
            :disabled="loading"
            class="w-full py-3 bg-primary-600 text-white font-semibold rounded-lg hover:bg-primary-700 transition disabled:opacity-50"
            data-testid="forgot-submit-btn"
          >
            {{ loading ? 'Enviando...' : 'Enviar instruções' }}
          </button>

          <div class="text-center">
            <router-link
              to="/login"
              class="text-sm text-primary-600 hover:text-primary-700 font-medium"
              data-testid="back-to-login-link"
            >
              Voltar para o login
            </router-link>
          </div>
        </form>

        <!-- Success state -->
        <div v-else class="text-center space-y-4" data-testid="forgot-success">
          <div class="mx-auto w-12 h-12 bg-green-100 rounded-full flex items-center justify-center">
            <svg class="w-6 h-6 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7" />
            </svg>
          </div>
          <h2 class="text-lg font-semibold text-gray-900">Solicitação recebida</h2>
          <p class="text-sm text-gray-600">
            Se o e-mail informado estiver cadastrado, você receberá as instruções
            de recuperação de senha.
          </p>
          <p v-if="devToken" class="text-xs text-gray-400 bg-gray-50 p-3 rounded-md break-all" data-testid="dev-reset-token">
            <strong>AMBIENTE DE DESENVOLVIMENTO:</strong> seu token de redefinição é<br>
            <code>{{ devToken }}</code>
          </p>
          <p v-if="devToken" class="text-xs text-gray-500">
            Use este token na tela de redefinição de senha. Em produção, o token seria enviado por e-mail.
          </p>
          <router-link
            to="/login"
            class="inline-block text-sm text-primary-600 hover:text-primary-700 font-medium"
          >
            Voltar para o login
          </router-link>
        </div>
      </div>
    </main>

    <footer class="bg-gray-100 py-4 text-center text-sm text-gray-500">
      &copy; {{ new Date().getFullYear() }} {{ tenantName }}. Todos os direitos reservados.
    </footer>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useTenantStore } from '../stores/tenant'
import AppAlert from '../components/AppAlert.vue'
import api from '../api/client'

const tenantStore = useTenantStore()
const tenantName = computed(() => tenantStore.name || 'Plataforma de Cursos')

const email = ref('')
const loading = ref(false)
const error = ref('')
const submitted = ref(false)
const devToken = ref('')

async function handleSubmit() {
  loading.value = true
  error.value = ''
  try {
    const response = await api.post('/api/v1/auth/forgot-password', {
      email: email.value,
    })
    // In dev/test, backend returns reset_token
    if (response.data?.reset_token) {
      devToken.value = response.data.reset_token
    }
    submitted.value = true
  } catch (err) {
    // Generic response — don't reveal whether email exists
    submitted.value = true
  } finally {
    loading.value = false
  }
}
</script>
