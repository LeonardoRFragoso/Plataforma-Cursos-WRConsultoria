<template>
  <header
    class="sticky top-0 z-20 bg-white border-b border-gray-200"
    data-testid="app-topbar"
  >
    <div class="flex h-16 items-center justify-between px-4 md:px-6">
      <div class="flex items-center gap-3 min-w-0">
        <!-- Mobile menu trigger -->
        <button
          type="button"
          class="md:hidden inline-flex items-center justify-center rounded-md p-2 text-gray-600 hover:text-primary-600 hover:bg-gray-50"
          :aria-expanded="open ? 'true' : 'false'"
          aria-controls="app-sidebar"
          aria-label="Abrir menu de navegação"
          data-testid="mobile-menu-toggle"
          @click="$emit('toggle-drawer')"
        >
          <svg
            v-if="!open" class="h-6 w-6" fill="none" stroke="currentColor"
            viewBox="0 0 24 24" stroke-width="2"
          >
            <path stroke-linecap="round" stroke-linejoin="round" d="M4 6h16M4 12h16M4 18h16" />
          </svg>
          <svg
            v-else class="h-6 w-6" fill="none" stroke="currentColor"
            viewBox="0 0 24 24" stroke-width="2"
          >
            <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>

        <!-- Breadcrumb / page context -->
        <div class="min-w-0">
          <p
            v-if="tenantStore.loading && !tenantStore.loaded"
            class="truncate text-sm text-gray-400"
            data-testid="topbar-brand-loading"
          >
            Carregando…
          </p>
          <p v-else class="truncate text-sm font-semibold text-secondary-900">
            {{ currentpageTitle }}
          </p>
          <p class="truncate text-xs text-gray-500">{{ tenantStore.name || 'Plataforma' }}</p>
        </div>
      </div>

      <!-- User context with avatar -->
      <div class="flex items-center gap-3">
        <div class="hidden sm:block text-right">
          <p class="text-sm font-medium text-secondary-900 truncate max-w-[180px]">
            {{ authStore.user?.full_name || authStore.user?.email || '—' }}
          </p>
          <p class="text-xs text-gray-500">{{ roleLabel }}</p>
        </div>
        <!-- Avatar initials -->
        <div
          class="flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-xs font-bold text-white"
          :style="avatarStyle"
          :title="authStore.user?.full_name || ''"
        >
          {{ initials }}
        </div>
        <button
          type="button"
          @click="handleLogout"
          class="rounded-md px-3 py-2 text-sm font-medium text-gray-600 hover:text-red-600 hover:bg-gray-50 transition-colors"
          data-testid="topbar-logout"
        >
          Sair
        </button>
      </div>
    </div>
  </header>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { useTenantStore } from '../stores/tenant'

defineProps({
  open: { type: Boolean, default: false },
})

defineEmits(['toggle-drawer'])

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const tenantStore = useTenantStore()

const roleMap = {
  admin: 'Administrador',
  student: 'Aluno',
  super_admin: 'Super Administrador',
}

const roleLabel = computed(
  () => roleMap[authStore.userRole?.toLowerCase()] || authStore.userRole || '—'
)

const PAGE_TITLES = {
  '/dashboard': 'Dashboard',
  '/cursos': 'Catálogo',
  '/certificates': 'Meus Certificados',
  '/courses': 'Cursos',
  '/classes': 'Turmas',
  '/students': 'Alunos',
  '/enrollments': 'Matrículas',
  '/payments': 'Pagamentos',
  '/settings/white-label': 'White Label',
  '/super-admin': 'Gestão Global',
}

const currentpageTitle = computed(() => {
  const path = route.path
  // Try exact match
  if (PAGE_TITLES[path]) return PAGE_TITLES[path]
  // Try prefix match for nested routes
  for (const key of Object.keys(PAGE_TITLES)) {
    if (path.startsWith(key + '/')) return PAGE_TITLES[key]
  }
  return tenantStore.name || 'Plataforma'
})

const initials = computed(() => {
  const name = authStore.user?.full_name || ''
  if (!name) return '?'
  const parts = name.trim().split(/\s+/)
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase()
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase()
})

const avatarStyle = computed(() => {
  const primary = tenantStore.primary_color || '#0056b3'
  const secondary = tenantStore.secondary_color || '#1a1a1a'
  return { background: `linear-gradient(135deg, ${primary}, ${secondary})` }
})

const handleLogout = () => {
  authStore.logout()
  router.push('/login')
}
</script>
