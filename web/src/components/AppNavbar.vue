<template>
  <nav class="bg-white shadow-md border-b border-gray-200">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-3 flex justify-between items-center">
      <router-link to="/" class="flex items-center">
        <img v-if="tenantStore.logo_url" :src="tenantStore.logo_url" :alt="tenantStore.name" class="h-12 w-auto" />
        <span v-else class="text-xl font-bold text-primary-600">{{ tenantStore.name || 'Plataforma' }}</span>
      </router-link>
      <div class="flex items-center space-x-4">
        <template v-if="authStore.isAuthenticated">
          <router-link to="/dashboard" class="text-gray-700 hover:text-primary-600 font-medium text-sm transition-colors">
            Dashboard
          </router-link>
          <button
            @click="handleLogout"
            class="text-primary-600 hover:text-primary-700 font-medium text-sm transition-colors"
          >
            Sair
          </button>
        </template>
        <template v-else>
          <router-link to="/login" class="text-gray-700 hover:text-primary-600 font-medium text-sm transition-colors">
            Login
          </router-link>
          <router-link
            to="/register"
            class="bg-primary-600 text-white px-4 py-2 rounded-md hover:bg-primary-700 font-semibold text-sm transition-colors"
          >
            Cadastre-se
          </router-link>
        </template>
      </div>
    </div>
  </nav>
</template>

<script setup>
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { useTenantStore } from '../stores/tenant'

const router = useRouter()
const authStore = useAuthStore()
const tenantStore = useTenantStore()

const handleLogout = () => {
  authStore.logout()
  router.push('/login')
}
</script>
