<template>
  <div class="min-h-screen bg-gray-50 flex items-center justify-center">
    <div class="text-center">
      <h1 class="text-6xl font-bold text-red-600 mb-4">403</h1>
      <p class="text-xl text-gray-600 mb-8">Acesso negado</p>
      <p class="text-gray-500 mb-8">Você não tem permissão para acessar esta página.</p>
      <router-link
        :to="homeRoute"
        class="bg-primary-600 text-white px-6 py-3 rounded-md hover:bg-primary-700 transition-colors font-semibold"
        data-testid="forbidden-home-link"
      >
        Voltar ao início
      </router-link>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useAuthStore } from '../stores/auth'
import { getHomeRoute } from '../utils/homeRoute'

const authStore = useAuthStore()
const homeRoute = computed(() => getHomeRoute(authStore))
</script>
