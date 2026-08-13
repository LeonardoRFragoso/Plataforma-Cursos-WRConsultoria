<template>
  <div class="min-h-screen bg-gray-50">
    <AppNavbar />
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <h1 class="text-3xl font-bold text-secondary-900 mb-8">Matrículas</h1>
      <div class="bg-white p-6 rounded-lg shadow-md border border-gray-200">
        <p class="text-gray-600">Gerenciamento de matrículas em desenvolvimento...</p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import AppNavbar from '../components/AppNavbar.vue'

const router = useRouter()
const authStore = useAuthStore()

const handleLogout = () => {
  authStore.logout()
  router.push('/login')
}
</script>
