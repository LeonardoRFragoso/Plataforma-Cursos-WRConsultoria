<template>
  <div class="min-h-screen bg-gradient-to-br from-primary-50 to-gray-50 flex items-center justify-center">
    <div class="bg-white p-8 rounded-lg shadow-lg w-full max-w-md border border-gray-200">
      <div class="text-center mb-6">
        <div class="text-3xl font-bold text-primary-600 mb-2">WR</div>
        <h2 class="text-2xl font-bold text-secondary-900">Cadastro</h2>
      </div>
      
      <form @submit.prevent="handleRegister" class="space-y-4">
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">Nome Completo</label>
          <input
            v-model="fullName"
            type="text"
            required
            class="w-full px-4 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent"
            placeholder="Seu nome"
          />
        </div>

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

        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">Confirmar Senha</label>
          <input
            v-model="confirmPassword"
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
          {{ loading ? 'Cadastrando...' : 'Cadastrar' }}
        </button>
      </form>

      <div v-if="error" class="mt-4 p-4 bg-red-50 border border-red-200 rounded-md text-red-700 text-sm">
        {{ error }}
      </div>

      <div v-if="success" class="mt-4 p-4 bg-green-50 border border-green-200 rounded-md text-green-700 text-sm">
        Cadastro realizado com sucesso! Faça login para continuar.
      </div>

      <div class="mt-6 text-center">
        <p class="text-gray-600">
          Já tem conta?
          <router-link to="/login" class="text-primary-600 hover:text-primary-700 font-semibold">
            Faça login
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

const fullName = ref('')
const email = ref('')
const password = ref('')
const confirmPassword = ref('')
const loading = ref(false)
const error = ref('')
const success = ref(false)

const handleRegister = async () => {
  if (password.value !== confirmPassword.value) {
    error.value = 'As senhas não coincidem'
    return
  }

  loading.value = true
  error.value = ''
  success.value = false
  
  try {
    await authStore.register(email.value, fullName.value, password.value)
    success.value = true
    setTimeout(() => {
      router.push('/login')
    }, 2000)
  } catch (err) {
    error.value = 'Erro ao cadastrar. Tente novamente.'
  } finally {
    loading.value = false
  }
}
</script>
