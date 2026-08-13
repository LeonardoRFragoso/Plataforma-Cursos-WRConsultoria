<template>
  <nav class="bg-primary-700 shadow-lg">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-3 flex justify-between items-center">
      <router-link to="/dashboard" class="flex items-center">
        <img src="../assets/brand/logo-wr-color.png" alt="WR Consultoria e Soluções em QSMS" class="h-12 w-auto" />
      </router-link>
      <div class="flex items-center space-x-4">
        <span class="text-white/80 text-sm hidden sm:inline">{{ authStore.user?.full_name }}</span>
        <button
          @click="handleLogout"
          class="text-white hover:text-accent-400 font-medium text-sm transition-colors"
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

const router = useRouter()
const authStore = useAuthStore()

const handleLogout = () => {
  authStore.logout()
  router.push('/login')
}
</script>
