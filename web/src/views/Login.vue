<template>
  <div class="min-h-screen flex flex-col">
    <!-- Header branco com logo -->
    <header class="bg-white shadow-md border-b border-gray-200">
      <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-3 flex justify-between items-center">
        <router-link :to="homeRoute" class="flex items-center">
          <img v-if="tenantStore.logo_url" :src="tenantStore.logo_url" :alt="tenantStore.name" class="h-12 w-auto" />
          <span v-else class="text-xl font-bold text-primary-600">{{ tenantStore.name || 'Plataforma de Cursos' }}</span>
        </router-link>
        <AppLink to="/register" variant="primary">
          Cadastre-se
        </AppLink>
      </div>
    </header>

    <div class="flex-1 flex items-center justify-center bg-gray-50 py-12">
      <AppCard class="w-full max-w-md">
        <div class="text-center mb-6">
          <img v-if="tenantStore.logo_url" :src="tenantStore.logo_url" :alt="tenantStore.name" class="h-16 w-auto mx-auto mb-4" />
          <h2 class="text-2xl font-bold text-secondary-900">{{ tenantStore.name || 'Plataforma de Cursos' }}</h2>
        </div>
        
        <form @submit.prevent="handleLogin" class="space-y-4">
          <AppInput
            v-model="identifier"
            type="text"
            label="CPF ou E-mail"
            placeholder="CPF (11 dígitos) ou seu@email.com"
            required
          />

          <AppInput
            v-model="password"
            type="password"
            label="Senha"
            placeholder="••••••••"
            required
          />

          <AppButton type="submit" :disabled="loading" class="w-full">
            {{ loading ? 'Entrando...' : 'Entrar' }}
          </AppButton>
        </form>

        <div v-if="error" class="mt-4 p-4 bg-red-50 border border-red-200 rounded-md text-red-700 text-sm">
          {{ error }}
        </div>

        <div class="mt-6 text-center space-y-4">
          <p class="text-gray-600">
            Não tem conta?
            <AppLink to="/register" variant="primary">
              Cadastre-se
            </AppLink>
          </p>

          <div class="border-t border-gray-200 pt-4">
            <router-link
              to="/recuperar-senha"
              class="text-sm text-primary-600 hover:text-primary-700 font-medium"
              data-testid="forgot-password-link"
            >
              Esqueci minha senha
            </router-link>
          </div>
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
import { getHomeRoute } from '../utils/homeRoute'
import { resolveSafeRedirect } from '../utils/safeRedirect'
import AppCard from '../components/AppCard.vue'
import AppButton from '../components/AppButton.vue'
import AppInput from '../components/AppInput.vue'
import AppLink from '../components/AppLink.vue'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()
const tenantStore = useTenantStore()

const identifier = ref('')
const password = ref('')
const loading = ref(false)
const error = ref('')

const homeRoute = computed(() => getHomeRoute(authStore))

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
