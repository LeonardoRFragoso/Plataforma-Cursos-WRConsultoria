<template>
  <div class="min-h-screen bg-gray-50" data-testid="app-shell">
    <AppSidebar :open="drawerOpen" @close="drawerOpen = false" />

    <div class="md:ml-64 flex min-h-screen flex-col">
      <AppTopbar :open="drawerOpen" @toggle-drawer="toggleDrawer" />

      <main class="flex-1 min-w-0 w-full" data-testid="app-workspace">
        <div class="px-4 sm:px-6 lg:px-8 py-8" data-testid="app-workspace-inner">
          <slot />
        </div>
      </main>
    </div>
  </div>
</template>

<script setup>
/**
 * AuthenticatedLayout (AppShell) — persistent SaaS application shell.
 *
 *   ┌──────────────┬──────────────────────────────────────────┐
 *   │              │ TOPBAR                                   │
 *   │   SIDEBAR    ├──────────────────────────────────────────┤
 *   │  (persistent)│                                          │
 *   │              │              WORKSPACE                   │
 *   │              │       uses remaining viewport width      │
 *   └──────────────┴──────────────────────────────────────────┘
 *
 * The shell owns global navigation (sidebar + topbar) and the outer workspace
 * padding. Authenticated pages render their content directly into the
 * workspace slot — they must NOT re-instantiate global navigation or constrain
 * the root workspace to a centered max-width. Controlled-width content
 * (forms, settings, reading panels) may still use inner max-w-* utilities.
 */
import { ref, onMounted, onBeforeUnmount, watch } from 'vue'
import { useRoute } from 'vue-router'
import AppSidebar from '../components/AppSidebar.vue'
import AppTopbar from '../components/AppTopbar.vue'

const route = useRoute()
const drawerOpen = ref(false)

const toggleDrawer = () => {
  drawerOpen.value = !drawerOpen.value
}

// Close the mobile drawer whenever the route (workspace content) changes.
watch(
  () => route.path,
  () => {
    drawerOpen.value = false
  }
)

// Escape closes the mobile drawer.
const onKeydown = (e) => {
  if (e.key === 'Escape' && drawerOpen.value) {
    drawerOpen.value = false
  }
}

onMounted(() => {
  if (typeof document !== 'undefined') {
    document.addEventListener('keydown', onKeydown)
  }
})

onBeforeUnmount(() => {
  if (typeof document !== 'undefined') {
    document.removeEventListener('keydown', onKeydown)
    document.body.style.overflow = ''
  }
})
</script>
