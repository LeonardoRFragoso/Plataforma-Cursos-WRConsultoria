<template>
  <router-view />
</template>

<script setup>
import { onMounted } from 'vue'
import { useAuthStore } from './stores/auth'

const authStore = useAuthStore()

onMounted(async () => {
  if (authStore.token) {
    try {
      await authStore.initializeUser()
      console.log('✓ User initialized:', {
        role: authStore.userRole,
        name: authStore.user?.full_name,
        email: authStore.user?.email
      })
    } catch (error) {
      console.error('✗ Failed to initialize user:', error)
    }
  }
})
</script>

<style scoped>
</style>
