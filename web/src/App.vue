<template>
  <component :is="layoutComponent">
    <router-view />
  </component>

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
import { onMounted, computed } from 'vue'
import { useRoute } from 'vue-router'
import { useAuthStore } from './stores/auth'
import { useToast } from './composables/useToast'
import Toast from './components/Toast.vue'
import PublicLayout from './layouts/PublicLayout.vue'
import AuthenticatedLayout from './layouts/AuthenticatedLayout.vue'

const route = useRoute()
const authStore = useAuthStore()
const { toasts, removeToast } = useToast()

// Layout is chosen from route.meta.layout. Authenticated routes render inside
// the AppShell (sidebar + topbar + full-width workspace); everything else
// renders inside the centered PublicLayout. The layout component stays mounted
// across route changes so the shell remains stable while only the workspace
// content swaps.
const layoutComponent = computed(() =>
  route.meta.layout === 'authenticated' ? AuthenticatedLayout : PublicLayout
)

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
