<template>
  <div class="min-h-screen bg-secondary-50">
    <nav class="bg-white shadow-sm">
      <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4 flex justify-between items-center">
        <router-link to="/dashboard" class="text-2xl font-bold text-primary-600">WR Cursos</router-link>
        <button @click="handleLogout" class="text-red-600">Sair</button>
      </div>
    </nav>
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <h1 class="text-3xl font-bold text-primary-900 mb-8">Pagamentos</h1>
      <div class="bg-white p-6 rounded-lg shadow-md">
        <p class="text-secondary-600">Gerenciamento de pagamentos em desenvolvimento...</p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const authStore = useAuthStore()

const handleLogout = () => {
  authStore.logout()
  router.push('/login')
}
</script>
