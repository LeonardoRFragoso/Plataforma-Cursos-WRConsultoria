<template>
  <AuthLayout>
    <div class="bg-white rounded-xl shadow-lg border border-gray-200 p-8 sm:p-10" data-testid="sso-callback-card">
      <!-- Loading state -->
      <div v-if="loading" class="text-center py-6">
        <div class="inline-flex items-center justify-center w-12 h-12 rounded-full bg-primary-50 mb-4">
          <svg class="animate-spin h-6 w-6 text-primary-600" fill="none" viewBox="0 0 24 24" data-testid="sso-callback-spinner">
            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
        </div>
        <h1 class="text-lg font-bold text-secondary-900 mb-1" data-testid="sso-callback-loading-title">
          Entrando na Plataforma de Cursos...
        </h1>
        <p class="text-sm text-gray-500">Aguarde enquanto validamos sua sessão.</p>
      </div>

      <!-- Error state -->
      <div v-else-if="error" class="text-center py-6">
        <div class="inline-flex items-center justify-center w-12 h-12 rounded-full bg-red-50 mb-4">
          <svg class="h-6 w-6 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
          </svg>
        </div>
        <h1 class="text-lg font-bold text-secondary-900 mb-1" data-testid="sso-callback-error-title">
          Não foi possível entrar
        </h1>
        <p class="text-sm text-gray-600 mb-6" data-testid="sso-callback-error-message">{{ error }}</p>
        <button
          type="button"
          @click="goToLogin"
          class="w-full py-3 bg-primary-600 text-white font-semibold rounded-lg hover:bg-primary-700 transition-colors"
          data-testid="sso-callback-retry"
        >
          Tentar novamente
        </button>
      </div>
    </div>
  </AuthLayout>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import AuthLayout from '../layouts/AuthLayout.vue'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()

const loading = ref(true)
const error = ref('')

const goToLogin = () => {
  router.push('/login')
}

onMounted(async () => {
  const code = route.query.code
  const state = route.query.state

  if (!code || !state) {
    error.value = 'Parâmetros de autenticação ausentes. Tente entrar novamente pela Central WR.'
    loading.value = false
    return
  }

  try {
    await authStore.ssoLogin(code, state)
    router.push('/dashboard')
  } catch (err) {
    if (err.response?.status === 403) {
      error.value = err.response?.data?.detail || 'Apenas administradores podem acessar via SSO.'
    } else if (err.response?.status === 400) {
      error.value = err.response?.data?.detail || 'Código de autorização inválido ou expirado. Tente entrar novamente pela Central WR.'
    } else if (err.code === 'ERR_NETWORK' || !err.response) {
      error.value = 'Não foi possível conectar ao serviço. Tente novamente.'
    } else {
      error.value = err.response?.data?.detail || 'Ocorreu um erro durante a autenticação. Tente novamente.'
    }
    loading.value = false
  }
})
</script>
