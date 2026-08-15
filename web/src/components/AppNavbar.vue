<template>
  <nav class="bg-white shadow-md border-b border-gray-200">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-3 flex justify-between items-center">
      <router-link to="/dashboard" class="flex items-center">
        <img v-if="tenantStore.logo_url" :src="tenantStore.logo_url" :alt="tenantStore.name" class="h-12 w-auto" />
        <span v-else class="text-xl font-bold text-primary-600">{{ tenantStore.name || 'Plataforma' }}</span>
      </router-link>
      <div class="flex items-center space-x-4">
        <span class="text-gray-700 text-sm hidden sm:inline">{{ authStore.user?.full_name }}</span>
        <button
          @click="handleLogout"
          class="text-primary-600 hover:text-primary-700 font-medium text-sm transition-colors"
        >
          Sair
        </button>
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
