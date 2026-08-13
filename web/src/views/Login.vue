<template>
  <div class="min-h-screen bg-gradient-to-br from-primary-50 to-gray-50 flex items-center justify-center">
    <div class="bg-white p-8 rounded-lg shadow-lg w-full max-w-md border border-gray-200">
      <div class="text-center mb-6">
        <div class="text-3xl font-bold text-primary-600 mb-2">WR</div>
        <h2 class="text-2xl font-bold text-secondary-900">Plataforma de Cursos</h2>
      </div>
      
      <form @submit.prevent="handleLogin" class="space-y-4">
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">Email</label>
          <input
            v-model="email"
            type="email"
            required
            class="w-full px-4 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent"
            placeholder="seu@email.com"
          />
        </div>

        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">Senha</label>
          <input
            v-model="password"
            type="password"
            required
            class="w-full px-4 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent"
            placeholder="••••••••"
          />
        </div>

        <button
          type="submit"
          :disabled="loading"
          class="w-full bg-primary-600 text-white py-2 rounded-md hover:bg-primary-700 disabled:opacity-50 font-semibold transition-colors"
        >
          {{ loading ? 'Entrando...' : 'Entrar' }}
        </button>
      </form>

      <div v-if="error" class="mt-4 p-4 bg-red-50 border border-red-200 rounded-md text-red-700 text-sm">
        {{ error }}
      </div>

      <div class="mt-6 text-center">
        <p class="text-gray-600">
          Não tem conta?
          <router-link to="/register" class="text-primary-600 hover:text-primary-700 font-semibold">
            Cadastre-se
          </router-link>
        </p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const authStore = useAuthStore()

const email = ref('')
const password = ref('')
const loading = ref(false)
const error = ref('')

const handleLogin = async () => {
  loading.value = true
  error.value = ''
  
  try {
    await authStore.login(email.value, password.value)
    router.push('/dashboard')
  } catch (err) {
    error.value = 'Email ou senha inválidos'
  } finally {
    loading.value = false
  }
}
</script>
