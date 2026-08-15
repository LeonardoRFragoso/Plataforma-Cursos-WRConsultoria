<template>
  <div class="min-h-screen flex flex-col">
    <!-- Header branco com logo -->
    <header class="bg-white shadow-md border-b border-gray-200">
      <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-3 flex justify-between items-center">
        <router-link to="/" class="flex items-center">
          <img v-if="tenantStore.logo_url" :src="tenantStore.logo_url" :alt="tenantStore.name" class="h-12 w-auto" />
          <span v-else class="text-xl font-bold text-primary-600">{{ tenantStore.name || 'Plataforma de Cursos' }}</span>
        </router-link>
        <AppLink to="/login" variant="primary">
          Login
        </AppLink>
      </div>
    </header>

    <div class="flex-1 flex items-center justify-center bg-gray-50 py-12">
      <AppCard class="w-full max-w-md">
        <div class="text-center mb-6">
          <img v-if="tenantStore.logo_url" :src="tenantStore.logo_url" :alt="tenantStore.name" class="h-16 w-auto mx-auto mb-4" />
          <h2 class="text-2xl font-bold text-secondary-900">Cadastro</h2>
        </div>
      
        <form @submit.prevent="handleRegister" class="space-y-4">
          <AppInput
            v-model="fullName"
            type="text"
            label="Nome Completo"
            placeholder="Seu nome"
            required
          />

          <AppInput
            v-model="email"
            type="email"
            label="Email"
            placeholder="seu@email.com"
            required
          />

          <AppInput
            v-model="password"
            type="password"
            label="Senha"
            placeholder="••••••••"
            required
          />

          <AppInput
            v-model="confirmPassword"
            type="password"
            label="Confirmar Senha"
            placeholder="••••••••"
            required
            :error="passwordError"
          />

          <AppButton type="submit" :disabled="loading" class="w-full">
            {{ loading ? 'Cadastrando...' : 'Cadastrar' }}
          </AppButton>
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
            <AppLink :to="{ path: '/login', query: { redirect: route.query.redirect } }" variant="primary">
              Faça login
            </AppLink>
          </p>
        </div>
      </AppCard>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { useTenantStore } from '../stores/tenant'
import AppCard from '../components/AppCard.vue'
import AppButton from '../components/AppButton.vue'
import AppInput from '../components/AppInput.vue'
import AppLink from '../components/AppLink.vue'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()
const tenantStore = useTenantStore()

const fullName = ref('')
const email = ref('')
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
    await authStore.register(email.value, fullName.value, password.value)
    success.value = true
    setTimeout(() => {
      const redirect = route.query.redirect || '/dashboard'
      router.push({ path: '/login', query: { redirect } })
    }, 2000)
  } catch (err) {
    error.value = 'Erro ao cadastrar. Tente novamente.'
  } finally {
    loading.value = false
  }
}
</script>
