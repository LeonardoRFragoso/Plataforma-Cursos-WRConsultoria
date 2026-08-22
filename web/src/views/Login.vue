<template>
  <AuthLayout>
    <div class="bg-white rounded-xl shadow-lg border border-gray-200 p-8 sm:p-10" data-testid="login-card">
      <div class="mb-8">
        <h1 class="text-2xl font-bold text-secondary-900 mb-2">Acesse sua conta</h1>
        <p class="text-sm text-gray-500">Entre para acessar seus cursos e certificados.</p>
      </div>

      <form @submit.prevent="handleLogin" class="space-y-5">
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1.5">CPF ou E-mail</label>
          <input
            v-model="identifier"
            type="text"
            required
            placeholder="CPF (11 dígitos) ou seu@email.com"
            class="w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-colors"
            data-testid="login-identifier"
          />
        </div>

        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1.5">Senha</label>
          <input
            v-model="password"
            type="password"
            required
            placeholder="••••••••"
            class="w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-colors"
            data-testid="login-password"
          />
        </div>

        <button
          type="submit"
          :disabled="loading"
          class="w-full py-3 bg-primary-600 text-white font-semibold rounded-lg hover:bg-primary-700 transition-colors disabled:opacity-60 disabled:cursor-not-allowed"
          data-testid="login-submit"
        >
          {{ loading ? 'Entrando...' : 'Entrar' }}
        </button>
      </form>

      <div v-if="error" class="mt-4 p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm" data-testid="login-error">
        {{ error }}
      </div>

      <div class="mt-8 space-y-3">
        <div class="text-center">
          <p class="text-sm text-gray-600">
            Não tem conta?
            <router-link
              :to="registerLinkTo"
              class="text-primary-600 hover:text-primary-700 font-semibold"
              data-testid="login-register-link"
            >
              Cadastre-se
            </router-link>
          </p>
        </div>
        <div class="border-t border-gray-100 pt-3 text-center">
          <router-link
            :to="forgotPasswordLinkTo"
            class="text-sm text-primary-600 hover:text-primary-700 font-medium"
            data-testid="forgot-password-link"
          >
            Esqueci minha senha
          </router-link>
        </div>
      </div>
    </div>
  </AuthLayout>
</template>

<script setup>
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { resolveSafeRedirect } from '../utils/safeRedirect'
import AuthLayout from '../layouts/AuthLayout.vue'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()

const identifier = ref('')
const password = ref('')
const loading = ref(false)
const error = ref('')

// Computed link destinations that preserve the redirect query param.
const registerLinkTo = computed(() => {
  const redirect = route.query.redirect
  return redirect
    ? { path: '/register', query: { redirect } }
    : { path: '/register' }
})

const forgotPasswordLinkTo = computed(() => {
  const redirect = route.query.redirect
  return redirect
    ? { path: '/recuperar-senha', query: { redirect } }
    : { path: '/recuperar-senha' }
})

const handleLogin = async () => {
  loading.value = true
  error.value = ''

  try {
    await authStore.login(identifier.value, password.value)
    // Use safe redirect resolver — validates internal path + role authorization
    const redirect = resolveSafeRedirect(route.query.redirect, authStore)
    router.push(redirect)
  } catch (err) {
    // Distinguish 401 (invalid credentials) from network/server errors
    if (err.response?.status === 401) {
      error.value = 'CPF/E-mail ou senha inválidos'
    } else if (err.code === 'ERR_NETWORK' || !err.response) {
      error.value = 'Não foi possível conectar ao serviço. Tente novamente.'
    } else if (err.response?.status >= 500) {
      error.value = 'Não foi possível conectar ao serviço. Tente novamente.'
    } else {
      error.value = err.response?.data?.detail || 'CPF/E-mail ou senha inválidos'
    }
  } finally {
    loading.value = false
  }
}
</script>
