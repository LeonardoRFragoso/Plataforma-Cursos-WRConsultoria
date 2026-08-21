<template>
  <div class="min-h-screen bg-gray-50 flex flex-col">
    <header class="bg-primary-600 text-white py-6">
      <div class="max-w-3xl mx-auto px-4 text-center">
        <h1 class="text-2xl font-bold">Redefinir senha</h1>
        <p class="text-white/80 text-sm mt-1">Defina uma nova senha para sua conta.</p>
      </div>
    </header>

    <main class="flex-1 flex items-center justify-center p-6">
      <div class="w-full max-w-md bg-white rounded-lg shadow-lg p-8">
        <!-- Success state -->
        <div v-if="success" class="text-center space-y-4" data-testid="reset-success">
          <div class="mx-auto w-12 h-12 bg-green-100 rounded-full flex items-center justify-center">
            <svg class="w-6 h-6 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7" />
            </svg>
          </div>
          <h2 class="text-lg font-semibold text-gray-900">Senha redefinida!</h2>
          <p class="text-sm text-gray-600">Sua senha foi atualizada com sucesso. Você já pode fazer login.</p>
          <router-link
            to="/login"
            class="inline-block bg-primary-600 text-white px-6 py-2 rounded-md text-sm font-medium hover:bg-primary-700"
            data-testid="reset-go-login"
          >
            Ir para o login
          </router-link>
        </div>

        <!-- Form -->
        <form v-else class="space-y-4" @submit.prevent="handleSubmit">
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">Token de recuperação</label>
            <input
              v-model="token"
              type="text"
              required
              placeholder="Cole o token recebido"
              class="w-full p-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-600 font-mono text-sm"
              data-testid="reset-token-input"
            />
          </div>

          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">Nova senha</label>
            <input
              v-model="newPassword"
              type="password"
              required
              minlength="6"
              placeholder="Mínimo 6 caracteres"
              class="w-full p-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-600"
              data-testid="reset-password-input"
            />
          </div>

          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">Confirmar nova senha</label>
            <input
              v-model="confirmPassword"
              type="password"
              required
              minlength="6"
              placeholder="Repita a nova senha"
              class="w-full p-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-600"
              data-testid="reset-confirm-input"
            />
          </div>

          <AppAlert v-if="error" type="error" data-testid="reset-error">{{ error }}</AppAlert>

          <button
            type="submit"
            :disabled="loading"
            class="w-full py-3 bg-primary-600 text-white font-semibold rounded-lg hover:bg-primary-700 transition disabled:opacity-50"
            data-testid="reset-submit-btn"
          >
            {{ loading ? 'Redefinindo...' : 'Redefinir senha' }}
          </button>

          <div class="text-center">
            <router-link
              to="/login"
              class="text-sm text-primary-600 hover:text-primary-700 font-medium"
            >
              Voltar para o login
            </router-link>
          </div>
        </form>
      </div>
    </main>

    <footer class="bg-gray-100 py-4 text-center text-sm text-gray-500">
      &copy; {{ new Date().getFullYear() }} {{ tenantName }}. Todos os direitos reservados.
    </footer>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useTenantStore } from '../stores/tenant'
import AppAlert from '../components/AppAlert.vue'
import api from '../api/client'

const route = useRoute()
const tenantStore = useTenantStore()
const tenantName = computed(() => tenantStore.name || 'Plataforma de Cursos')

const token = ref('')
const newPassword = ref('')
const confirmPassword = ref('')
const loading = ref(false)
const error = ref('')
const success = ref(false)

onMounted(() => {
  // Support token via query param (e.g. from email link)
  if (route.query.token) {
    token.value = route.query.token
  }
})

async function handleSubmit() {
  error.value = ''

  if (newPassword.value !== confirmPassword.value) {
    error.value = 'As senhas não coincidem'
    return
  }

  if (newPassword.value.length < 6) {
    error.value = 'A senha deve ter no mínimo 6 caracteres'
    return
  }

  loading.value = true
  try {
    await api.post('/api/v1/auth/reset-password', {
      token: token.value,
      new_password: newPassword.value,
    })
    success.value = true
  } catch (err) {
    if (err.response?.status === 400) {
      error.value = 'Token inválido ou expirado. Solicite uma nova recuperação de senha.'
    } else if (!err.response) {
      error.value = 'Não foi possível conectar ao serviço. Tente novamente.'
    } else {
      error.value = 'Não foi possível redefinir a senha. Tente novamente.'
    }
  } finally {
    loading.value = false
  }
}
</script>
