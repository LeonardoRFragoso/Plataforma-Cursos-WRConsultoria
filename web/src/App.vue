<template>
  <router-view />

  <!-- Global toast container -->
  <Toast
    v-for="t in toasts"
    :key="t.id"
    :type="t.type"
    :title="t.title"
    :message="t.message"
    :duration="t.duration"
    @dismiss="removeToast(t.id)"
  />
</template>

<script setup>
import { onMounted } from 'vue'
import { useAuthStore } from './stores/auth'
import { useToast } from './composables/useToast'
import Toast from './components/Toast.vue'

const authStore = useAuthStore()
const { toasts, removeToast } = useToast()

onMounted(async () => {
  if (authStore.token) {
    try {
      await authStore.initializeUser()
    } catch (error) {
      // Silent — the API interceptor handles logout/redirect
    }
  }
})
</script>

<style scoped>
</style>
