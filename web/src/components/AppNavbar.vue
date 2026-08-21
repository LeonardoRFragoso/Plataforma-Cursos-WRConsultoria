<template>
  <nav class="bg-white shadow-md border-b border-gray-200">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-3 flex justify-between items-center">
      <router-link :to="homeRoute" class="flex items-center" data-testid="navbar-logo">
        <img v-if="tenantStore.logo_url" :src="tenantStore.logo_url" :alt="tenantStore.name" class="h-12 w-auto" />
        <span v-else class="text-xl font-bold text-primary-600">{{ tenantStore.name || 'Plataforma' }}</span>
      </router-link>

      <!-- Desktop nav -->
      <div class="hidden md:flex items-center space-x-1">
        <template v-if="authStore.isAuthenticated">
          <!-- Flat links (Dashboard, etc.) -->
          <router-link
            v-for="link in flatLinks"
            :key="link.to"
            :to="link.to"
            :class="[
              'font-medium text-sm px-3 py-2 rounded-md transition-colors',
              isActive(link.to)
                ? 'text-primary-600 bg-primary-50'
                : 'text-gray-700 hover:text-primary-600 hover:bg-gray-50'
            ]"
            :data-testid="'nav-link-' + link.testid"
          >
            {{ link.label }}
          </router-link>

          <!-- Dropdown groups -->
          <div
            v-for="group in dropdownGroups"
            :key="group.label"
            class="relative"
            @mouseenter="openDropdown = group.label"
            @mouseleave="openDropdown = null"
          >
            <button
              @click="toggleDropdown(group.label)"
              :class="[
                'font-medium text-sm px-3 py-2 rounded-md transition-colors flex items-center gap-1',
                isGroupActive(group)
                  ? 'text-primary-600 bg-primary-50'
                  : 'text-gray-700 hover:text-primary-600 hover:bg-gray-50'
              ]"
              :data-testid="'nav-group-' + group.testid"
              :aria-expanded="openDropdown === group.label"
              :aria-controls="'dropdown-' + group.testid"
            >
              {{ group.label }}
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
                <path stroke-linecap="round" stroke-linejoin="round" d="M19 9l-7 7-7-7" />
              </svg>
            </button>
            <div
              v-if="openDropdown === group.label"
              :id="'dropdown-' + group.testid"
              class="absolute right-0 mt-2 w-56 bg-white rounded-md shadow-lg border border-gray-200 py-1 z-50"
              :data-testid="'dropdown-panel-' + group.testid"
            >
              <router-link
                v-for="item in group.items"
                :key="item.to"
                :to="item.to"
                :class="[
                  'block px-4 py-2 text-sm transition-colors',
                  isActive(item.to)
                    ? 'text-primary-600 bg-primary-50'
                    : 'text-gray-700 hover:text-primary-600 hover:bg-gray-50'
                ]"
                :data-testid="'nav-link-' + item.testid"
              >
                {{ item.label }}
              </router-link>
            </div>
          </div>

          <!-- Logout -->
          <button
            @click="handleLogout"
            class="text-gray-500 hover:text-red-600 font-medium text-sm px-3 py-2 rounded-md transition-colors ml-2"
            data-testid="nav-logout"
          >
            Sair
          </button>
        </template>
        <template v-else>
          <router-link to="/cursos" class="text-gray-700 hover:text-primary-600 font-medium text-sm px-3 py-2 rounded-md transition-colors" data-testid="nav-link-catalog">
            Cursos
          </router-link>
          <router-link to="/validar-certificado" class="text-gray-700 hover:text-primary-600 font-medium text-sm px-3 py-2 rounded-md transition-colors" data-testid="nav-link-validate">
            Validar certificado
          </router-link>
          <router-link to="/seja-parceiro" class="text-gray-700 hover:text-primary-600 font-medium text-sm px-3 py-2 rounded-md transition-colors" data-testid="nav-link-partner">
            Seja parceiro
          </router-link>
          <router-link to="/login" class="text-gray-700 hover:text-primary-600 font-medium text-sm px-3 py-2 rounded-md transition-colors" data-testid="nav-link-login">
            Login
          </router-link>
          <router-link
            to="/register"
            class="bg-primary-600 text-white px-4 py-2 rounded-md hover:bg-primary-700 font-semibold text-sm transition-colors"
            data-testid="nav-link-register"
          >
            Cadastre-se
          </router-link>
        </template>
      </div>

      <!-- Mobile hamburger -->
      <button
        @click="mobileMenuOpen = !mobileMenuOpen"
        class="md:hidden text-gray-700 hover:text-primary-600"
        data-testid="mobile-menu-toggle"
        :aria-expanded="mobileMenuOpen"
        aria-controls="mobile-menu-panel"
        aria-label="Menu"
      >
        <svg v-if="!mobileMenuOpen" class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
          <path stroke-linecap="round" stroke-linejoin="round" d="M4 6h16M4 12h16M4 18h16" />
        </svg>
        <svg v-else class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
          <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
        </svg>
      </button>
    </div>

    <!-- Mobile menu panel -->
    <div
      v-if="mobileMenuOpen"
      id="mobile-menu-panel"
      class="md:hidden border-t border-gray-200 bg-white px-4 pb-4 space-y-1"
      data-testid="mobile-menu-panel"
    >
      <template v-if="authStore.isAuthenticated">
        <!-- Flat links -->
        <router-link
          v-for="link in flatLinks"
          :key="link.to"
          :to="link.to"
          @click="mobileMenuOpen = false"
          :class="[
            'block py-2 px-3 rounded-md font-medium text-sm transition-colors',
            isActive(link.to)
              ? 'text-primary-600 bg-primary-50'
              : 'text-gray-700 hover:text-primary-600 hover:bg-gray-50'
          ]"
          :data-testid="'mobile-nav-link-' + link.testid"
        >
          {{ link.label }}
        </router-link>

        <!-- Dropdown groups (expanded inline) -->
        <template v-for="group in dropdownGroups" :key="group.label">
          <div class="pt-2 pb-1 px-3 text-xs font-semibold text-gray-400 uppercase tracking-wide">
            {{ group.label }}
          </div>
          <router-link
            v-for="item in group.items"
            :key="item.to"
            :to="item.to"
            @click="mobileMenuOpen = false"
            :class="[
              'block py-2 px-3 rounded-md font-medium text-sm transition-colors',
              isActive(item.to)
                ? 'text-primary-600 bg-primary-50'
                : 'text-gray-700 hover:text-primary-600 hover:bg-gray-50'
            ]"
            :data-testid="'mobile-nav-link-' + item.testid"
          >
            {{ item.label }}
          </router-link>
        </template>

        <button
          @click="handleLogout"
          class="block w-full text-left py-2 px-3 rounded-md text-gray-500 hover:text-red-600 hover:bg-gray-50 font-medium text-sm transition-colors"
          data-testid="mobile-nav-logout"
        >
          Sair
        </button>
      </template>
      <template v-else>
        <router-link to="/cursos" @click="mobileMenuOpen = false" class="block py-2 px-3 rounded-md text-gray-700 hover:text-primary-600 hover:bg-gray-50 font-medium text-sm" data-testid="mobile-nav-link-catalog">
          Cursos
        </router-link>
        <router-link to="/validar-certificado" @click="mobileMenuOpen = false" class="block py-2 px-3 rounded-md text-gray-700 hover:text-primary-600 hover:bg-gray-50 font-medium text-sm" data-testid="mobile-nav-link-validate">
          Validar certificado
        </router-link>
        <router-link to="/seja-parceiro" @click="mobileMenuOpen = false" class="block py-2 px-3 rounded-md text-gray-700 hover:text-primary-600 hover:bg-gray-50 font-medium text-sm" data-testid="mobile-nav-link-partner">
          Seja parceiro
        </router-link>
        <router-link to="/login" @click="mobileMenuOpen = false" class="block py-2 px-3 rounded-md text-gray-700 hover:text-primary-600 hover:bg-gray-50 font-medium text-sm" data-testid="mobile-nav-link-login">
          Login
        </router-link>
        <router-link to="/register" @click="mobileMenuOpen = false" class="block py-2 px-3 rounded-md bg-primary-600 text-white hover:bg-primary-700 font-semibold text-sm" data-testid="mobile-nav-link-register">
          Cadastre-se
        </router-link>
      </template>
    </div>
  </nav>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { useTenantStore } from '../stores/tenant'
import { getHomeRoute } from '../utils/homeRoute'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()
const tenantStore = useTenantStore()

const mobileMenuOpen = ref(false)
const openDropdown = ref(null)

const homeRoute = computed(() => getHomeRoute(authStore))

// Navigation structure: flat links + dropdown groups per role
const navConfig = computed(() => {
  const role = authStore.userRole?.toLowerCase()
  if (!role) return { flat: [], groups: [] }

  if (role === 'student') {
    return {
      flat: [
        { to: '/dashboard', label: 'Dashboard', testid: 'dashboard' },
        { to: '/cursos', label: 'Meus Cursos', testid: 'my-courses' },
        { to: '/cursos', label: 'Catálogo', testid: 'catalog' },
        { to: '/certificates', label: 'Certificados', testid: 'certificates' },
      ],
      groups: [],
    }
  }

  if (role === 'admin') {
    return {
      flat: [
        { to: '/dashboard', label: 'Dashboard', testid: 'dashboard' },
      ],
      groups: [
        {
          label: 'Gestão',
          testid: 'management',
          items: [
            { to: '/courses', label: 'Cursos', testid: 'courses' },
            { to: '/classes', label: 'Turmas', testid: 'classes' },
            { to: '/students', label: 'Alunos', testid: 'students' },
            { to: '/enrollments', label: 'Matrículas', testid: 'enrollments' },
            { to: '/payments', label: 'Pagamentos', testid: 'payments' },
          ],
        },
        {
          label: 'Certificados',
          testid: 'certificates-group',
          items: [
            { to: '/certificates', label: 'Certificados', testid: 'certificates' },
          ],
        },
        {
          label: 'Personalização',
          testid: 'customization',
          items: [
            { to: '/settings/white-label', label: 'White Label', testid: 'white-label' },
          ],
        },
      ],
    }
  }

  if (role === 'super_admin') {
    return {
      flat: [
        { to: '/super-admin', label: 'Gestão Global', testid: 'super-admin' },
      ],
      groups: [],
    }
  }

  return { flat: [], groups: [] }
})

const flatLinks = computed(() => navConfig.value.flat)
const dropdownGroups = computed(() => navConfig.value.groups)

const isActive = (path) => {
  if (route.path === path) return true
  if (route.path.startsWith(path + '/')) return true
  return false
}

const isGroupActive = (group) => {
  return group.items.some((item) => isActive(item.to))
}

const toggleDropdown = (label) => {
  openDropdown.value = openDropdown.value === label ? null : label
}

// Close dropdown and mobile menu on route change
watch(() => route.path, () => {
  openDropdown.value = null
  mobileMenuOpen.value = false
})

const handleLogout = () => {
  mobileMenuOpen.value = false
  authStore.logout()
  router.push('/login')
}
</script>
