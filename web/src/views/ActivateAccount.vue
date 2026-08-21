<template>
  <AuthLayout>
    <div class="bg-white rounded-xl shadow-lg border border-gray-200 p-8 sm:p-10" data-testid="activation-card">
      <div class="mb-8">
        <h1 class="text-2xl font-bold text-secondary-900 mb-2">Ativar conta</h1>
        <p class="text-sm text-gray-500">Defina sua senha para acessar a plataforma.</p>
      </div>

      <!-- Success state -->
      <div v-if="success" class="text-center space-y-4" data-testid="activation-success">
        <div class="mx-auto w-14 h-14 bg-green-100 rounded-full flex items-center justify-center">
          <svg class="w-7 h-7 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7" />
          </svg>
        </div>
        <h2 class="text-lg font-semibold text-secondary-900">Conta ativada com sucesso!</h2>
        <p class="text-sm text-gray-600">Sua conta foi ativada. Você já pode entrar na plataforma.</p>
        <router-link
          to="/login"
          class="inline-block bg-primary-600 text-white px-6 py-2.5 rounded-lg text-sm font-semibold hover:bg-primary-700 transition-colors"
          data-testid="activation-go-login"
        >
          Entrar na plataforma
        </router-link>
      </div>

      <!-- Missing token state -->
      <div v-else-if="!token" class="text-center space-y-4" data-testid="activation-missing-token">
        <div class="mx-auto w-14 h-14 bg-red-100 rounded-full flex items-center justify-center">
          <svg class="w-7 h-7 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M12 9v2m0 4h.01M5.07 19h13.86c1.54 0 2.5-1.67 1.73-3L13.73 4c-.77-1.33-2.69-1.33-3.46 0L3.34 16c-.77 1.33.19 3 1.73 3z" />
          </svg>
        </div>
        <h2 class="text-lg font-semibold text-secondary-900">Link de ativação inválido</h2>
        <p class="text-sm text-gray-600">O link de ativação não contém um token válido. Solicite um novo link ao administrador.</p>
        <router-link
          to="/login"
          class="inline-block text-sm text-primary-600 hover:text-primary-700 font-medium"
        >
          Voltar para o login
        </router-link>
      </div>

      <!-- Form -->
      <form v-else class="space-y-5" @submit.prevent="handleSubmit">
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1.5">Nova senha</label>
          <input
            v-model="newPassword"
            type="password"
            required
            minlength="6"
            placeholder="Mínimo 6 caracteres"
            class="w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-colors"
            data-testid="activation-password-input"
          />
        </div>

        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1.5">Confirmar nova senha</label>
          <input
            v-model="confirmPassword"
            type="password"
            required
            minlength="6"
            placeholder="Repita a nova senha"
            class="w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-colors"
            data-testid="activation-confirm-input"
          />
        </div>

        <div v-if="error" class="p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm" data-testid="activation-error">
          {{ error }}
        </div>

        <button
          type="submit"
          :disabled="loading"
          class="w-full py-3 bg-primary-600 text-white font-semibold rounded-lg hover:bg-primary-700 transition-colors disabled:opacity-60 disabled:cursor-not-allowed"
          data-testid="activation-submit-btn"
        >
          {{ loading ? 'Ativando...' : 'Ativar conta' }}
        </button>

        <div class="text-center pt-2">
          <router-link
            to="/login"
            class="text-sm text-primary-600 hover:text-primary-700 font-medium"
          >
            Voltar para o login
          </router-link>
        </div>
      </form>
    </div>
  </AuthLayout>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import AuthLayout from '../layouts/AuthLayout.vue'
import api from '../api/client'

const route = useRoute()

const token = ref('')
const newPassword = ref('')
const confirmPassword = ref('')
const loading = ref(false)
const error = ref('')
const success = ref(false)

onMounted(() => {
  // Token comes from the URL — user does NOT need to copy/paste it.
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
    await api.post('/api/v1/auth/activate', {
      token: token.value,
      new_password: newPassword.value,
    })
    success.value = true
  } catch (err) {
    if (err.response?.status === 400) {
      error.value = 'Token inválido ou expirado. Solicite um novo link de ativação ao administrador.'
    } else if (!err.response) {
      error.value = 'Não foi possível conectar ao serviço. Tente novamente.'
    } else {
      error.value = 'Não foi possível ativar a conta. Tente novamente.'
    }
  } finally {
    loading.value = false
  }
}
</script>
