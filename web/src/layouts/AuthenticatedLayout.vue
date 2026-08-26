<template>
  <div class="min-h-screen bg-[var(--surface-page)]" data-testid="app-shell">
    <div class="pointer-events-none fixed inset-0 overflow-hidden" aria-hidden="true">
      <div class="absolute -right-32 -top-40 h-96 w-96 rounded-full bg-primary-100/30 blur-3xl"></div>
      <div class="absolute bottom-0 left-1/3 h-72 w-72 rounded-full bg-slate-200/30 blur-3xl"></div>
    </div>

    <AppSidebar :open="drawerOpen" @close="drawerOpen = false" />

    <div class="relative md:ml-64 flex min-h-screen flex-col">
      <AppTopbar :open="drawerOpen" @toggle-drawer="toggleDrawer" />
      <main class="flex-1 min-w-0 w-full" data-testid="app-workspace">
        <div class="px-4 py-6 sm:px-6 sm:py-7 lg:px-8 xl:px-10 xl:py-8" data-testid="app-workspace-inner">
          <slot />
        </div>
      </main>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, watch } from 'vue'
import { useRoute } from 'vue-router'
import AppSidebar from '../components/AppSidebar.vue'
import AppTopbar from '../components/AppTopbar.vue'

const route = useRoute()
const drawerOpen = ref(false)
const toggleDrawer = () => { drawerOpen.value = !drawerOpen.value }
watch(() => route.path, () => { drawerOpen.value = false })
const onKeydown = (e) => { if (e.key === 'Escape' && drawerOpen.value) drawerOpen.value = false }
onMounted(() => { if (typeof document !== 'undefined') document.addEventListener('keydown', onKeydown) })
onBeforeUnmount(() => {
  if (typeof document !== 'undefined') {
    document.removeEventListener('keydown', onKeydown)
    document.body.style.overflow = ''
  }
})
</script>
