<template>
  <AuthLayout>
    <div class="bg-white rounded-xl shadow-lg border border-gray-200 p-8 sm:p-10" data-testid="register-card">
      <div class="mb-8">
        <h1 class="text-2xl font-bold text-secondary-900 mb-2">Crie sua conta</h1>
        <p class="text-sm text-gray-500">
          Cadastre-se para acessar cursos, acompanhar seu progresso e consultar seus certificados.
        </p>
      </div>

      <form @submit.prevent="handleRegister" class="space-y-5">
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1.5">Nome Completo</label>
          <input
            v-model="fullName"
            type="text"
            required
            placeholder="Seu nome"
            class="w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-colors"
            data-testid="register-fullname"
          />
        </div>

        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1.5">E-mail</label>
          <input
            v-model="email"
            type="email"
            required
            placeholder="seu@email.com"
            class="w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-colors"
            data-testid="register-email"
          />
        </div>

        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1.5">CPF</label>
          <input
            v-model="cpf"
            type="text"
            required
            placeholder="000.000.000-00"
            class="w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-colors"
            data-testid="register-cpf"
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
            data-testid="register-password"
          />
        </div>

        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1.5">Confirmar Senha</label>
          <input
            v-model="confirmPassword"
            type="password"
            required
            placeholder="••••••••"
            :class="[
              'w-full px-4 py-3 border rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 transition-colors',
              passwordError ? 'border-red-300' : 'border-gray-300 focus:border-primary-500'
            ]"
            data-testid="register-confirm"
          />
          <p v-if="passwordError" class="mt-1 text-xs text-red-600">{{ passwordError }}</p>
        </div>

        <button
          type="submit"
          :disabled="loading"
          class="w-full py-3 bg-primary-600 text-white font-semibold rounded-lg hover:bg-primary-700 transition-colors disabled:opacity-60 disabled:cursor-not-allowed"
          data-testid="register-submit"
        >
          {{ loading ? 'Cadastrando...' : 'Cadastrar' }}
        </button>
      </form>

      <div v-if="error" class="mt-4 p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm" data-testid="register-error">
        {{ error }}
      </div>

      <div v-if="success" class="mt-4 p-3 bg-green-50 border border-green-200 rounded-lg text-green-700 text-sm" data-testid="register-success">
        Cadastro realizado com sucesso! Faça login para continuar.
      </div>

      <div class="mt-6 text-center">
        <p class="text-sm text-gray-600">
          Já tem conta?
          <router-link :to="{ path: '/login', query: { redirect: route.query.redirect } }" class="text-primary-600 hover:text-primary-700 font-semibold" data-testid="register-login-link">
            Faça login
          </router-link>
        </p>
      </div>
    </div>
  </AuthLayout>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { resolveSafeRedirect } from '../utils/safeRedirect'
import AuthLayout from '../layouts/AuthLayout.vue'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()

const fullName = ref('')
const email = ref('')
const cpf = ref('')
const password = ref('')
const confirmPassword = ref('')
const loading = ref(false)
const error = ref('')
const success = ref(false)

const passwordError = computed(() => {
  if (confirmPassword.value && password.value !== confirmPassword.value) {
    return 'As senhas não coincidem'
  }
  return ''
})

const handleRegister = async () => {
  if (password.value !== confirmPassword.value) {
    error.value = 'As senhas não coincidem'
    return
  }

  loading.value = true
  error.value = ''
  success.value = false

  try {
    await authStore.register(email.value, fullName.value, password.value, cpf.value)
    success.value = true
    setTimeout(() => {
      // New students register as 'student' role → use safe redirect resolver
      const redirect = resolveSafeRedirect(route.query.redirect, 'student')
      router.push({ path: '/login', query: { redirect } })
    }, 2000)
  } catch (err) {
    error.value = 'Erro ao cadastrar. Tente novamente.'
  } finally {
    loading.value = false
  }
}
</script>
