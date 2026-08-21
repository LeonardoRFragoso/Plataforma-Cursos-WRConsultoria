<template>
  <nav class="bg-white shadow-md border-b border-gray-200">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-3 flex justify-between items-center">
      <router-link :to="homeRoute" class="flex items-center" data-testid="navbar-logo">
        <img v-if="tenantStore.logo_url" :src="tenantStore.logo_url" :alt="tenantStore.name" class="h-12 w-auto" />
        <span v-else class="text-xl font-bold text-primary-600">{{ tenantStore.name || 'Plataforma' }}</span>
      </router-link>

      <!-- Desktop nav -->
      <div class="hidden md:flex items-center space-x-4">
        <template v-if="authStore.isAuthenticated">
          <router-link
            v-for="link in visibleNavLinks"
            :key="link.to"
            :to="link.to"
            :class="[
              'font-medium text-sm transition-colors',
              isActive(link.to)
                ? 'text-primary-600 border-b-2 border-primary-600 pb-1'
                : 'text-gray-700 hover:text-primary-600'
            ]"
            :data-testid="'nav-link-' + link.testid"
          >
            {{ link.label }}
          </router-link>
          <button
            @click="handleLogout"
            class="text-primary-600 hover:text-primary-700 font-medium text-sm transition-colors"
            data-testid="nav-logout"
          >
            Sair
          </button>
        </template>
        <template v-else>
          <router-link to="/login" class="text-gray-700 hover:text-primary-600 font-medium text-sm transition-colors">
            Login
          </router-link>
          <router-link
            to="/register"
            class="bg-primary-600 text-white px-4 py-2 rounded-md hover:bg-primary-700 font-semibold text-sm transition-colors"
          >
            Cadastre-se
          </router-link>
        </template>
      </div>

      <!-- Mobile hamburger -->
      <button
        v-if="authStore.isAuthenticated"
        @click="mobileMenuOpen = !mobileMenuOpen"
        class="md:hidden text-gray-700 hover:text-primary-600"
        data-testid="mobile-menu-toggle"
        aria-label="Menu"
      >
        <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
          <path stroke-linecap="round" stroke-linejoin="round" d="M4 6h16M4 12h16M4 18h16" />
        </svg>
      </button>

      <!-- Mobile unauthenticated actions -->
      <div v-if="!authStore.isAuthenticated" class="md:hidden flex items-center space-x-3">
        <router-link to="/login" class="text-gray-700 hover:text-primary-600 font-medium text-sm transition-colors">
          Login
        </router-link>
        <router-link
          to="/register"
          class="bg-primary-600 text-white px-3 py-1.5 rounded-md hover:bg-primary-700 font-semibold text-sm transition-colors"
        >
          Cadastre-se
        </router-link>
      </div>
    </div>

    <!-- Mobile menu panel -->
    <div
      v-if="authStore.isAuthenticated && mobileMenuOpen"
      class="md:hidden border-t border-gray-200 bg-white px-4 pb-4 space-y-2"
      data-testid="mobile-menu-panel"
    >
      <router-link
        v-for="link in visibleNavLinks"
        :key="link.to"
        :to="link.to"
        @click="mobileMenuOpen = false"
        :class="[
          'block py-2 font-medium text-sm transition-colors',
          isActive(link.to)
            ? 'text-primary-600'
            : 'text-gray-700 hover:text-primary-600'
        ]"
      >
        {{ link.label }}
      </router-link>
      <button
        @click="handleLogout"
        class="block w-full text-left py-2 text-primary-600 hover:text-primary-700 font-medium text-sm transition-colors"
      >
        Sair
      </button>
    </div>
  </nav>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { useTenantStore } from '../stores/tenant'
import { getHomeRoute } from '../utils/homeRoute'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()
const tenantStore = useTenantStore()

const mobileMenuOpen = ref(false)

const homeRoute = computed(() => getHomeRoute(authStore))

const allNavLinks = [
  { to: '/dashboard', label: 'Dashboard', testid: 'dashboard', roles: ['admin', 'super_admin', 'student'] },
  { to: '/courses', label: 'Cursos', testid: 'courses', roles: ['admin', 'super_admin'] },
  { to: '/classes', label: 'Turmas', testid: 'classes', roles: ['admin', 'super_admin'] },
  { to: '/students', label: 'Alunos', testid: 'students', roles: ['admin', 'super_admin'] },
  { to: '/enrollments', label: 'Matrículas', testid: 'enrollments', roles: ['admin', 'super_admin'] },
  { to: '/payments', label: 'Pagamentos', testid: 'payments', roles: ['admin', 'super_admin'] },
  { to: '/certificates', label: 'Certificados', testid: 'certificates', roles: ['admin', 'super_admin', 'student'] },
  { to: '/settings/white-label', label: 'White Label', testid: 'white-label', roles: ['admin', 'super_admin'] },
  { to: '/super-admin', label: 'Super Admin', testid: 'super-admin', roles: ['super_admin'] },
]

const visibleNavLinks = computed(() => {
  const role = authStore.userRole?.toLowerCase()
  if (!role) return []
  return allNavLinks.filter((link) => link.roles.includes(role))
})

const isActive = (path) => {
  if (route.path === path) return true
  // Active state for nested routes (e.g. /courses/123/lessons under /courses)
  if (route.path.startsWith(path + '/')) return true
  return false
}

const handleLogout = () => {
  mobileMenuOpen.value = false
  authStore.logout()
  router.push('/login')
}
</script>
