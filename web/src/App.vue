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
//
// Catalog (/cursos) and course detail (/cursos/:id) are public pages, but when
// an authenticated STUDENT visits them we render inside the AppShell so the
// student keeps their sidebar/topbar context (Option A from PR #16). Public
// visitors and admins still get the PublicLayout.
const layoutComponent = computed(() => {
  if (route.meta.layout === 'authenticated') return AuthenticatedLayout
  if (route.meta.layout === 'public' && authStore.isAuthenticated && authStore.userRole?.toLowerCase() === 'student') {
    // Only upgrade the catalog-family pages to the authenticated shell
    if (route.path === '/cursos' || route.path.startsWith('/cursos/')) {
      return AuthenticatedLayout
    }
  }
  return PublicLayout
})

onMounted(() => {
  // Background session restoration for public routes. The router guard
  // already awaits initializeUser() for protected routes, so this call only
  // matters when a user with a stored token lands on a public page. It is
  // intentionally fire-and-forget — the public page renders immediately and
  // the session is restored (or silently cleared) in the background.
  if (authStore.token && !authStore.initialized) {
    authStore.initializeUser().catch(() => {
      // Silent — the API interceptor handles logout/redirect on 401
    })
  }
})
</script>

<style scoped>
</style>
