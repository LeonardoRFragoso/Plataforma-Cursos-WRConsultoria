<template>
  <nav class="bg-white shadow-md border-b border-gray-200" aria-label="Navegação principal">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-3">
      <div class="flex justify-between items-center">
        <router-link to="/" class="flex items-center" aria-label="Página inicial">
          <img src="../assets/brand/logo-wr-color.png" alt="WR Consultoria e Soluções em QSMS" class="h-12 w-auto" />
        </router-link>

        <!-- Desktop menu -->
        <div class="hidden md:flex items-center space-x-6">
          <template v-for="item in menuItems" :key="item.to">
            <router-link
              :to="item.to"
              :aria-label="item.label"
              class="text-sm font-medium transition-colors"
              :class="route?.path === item.to ? 'text-primary-600' : 'text-gray-700 hover:text-primary-600'"
              :aria-current="route?.path === item.to ? 'page' : undefined"
            >
              {{ item.text }}
            </router-link>
          </template>

          <span v-if="authStore.user" class="text-gray-700 text-sm hidden lg:inline">
            {{ authStore.user?.full_name }}
          </span>

          <button
            v-if="authStore.isAuthenticated"
            @click="handleLogout"
            class="text-primary-600 hover:text-primary-700 font-medium text-sm transition-colors"
            aria-label="Sair da conta"
          >
            Sair
          </button>

          <router-link
            v-else
            to="/login"
            class="text-primary-600 hover:text-primary-700 font-medium text-sm transition-colors"
            aria-label="Entrar"
          >
            Entrar
          </router-link>
        </div>

        <!-- Mobile toggle -->
        <button
          class="md:hidden p-2 rounded-md text-gray-700 hover:bg-gray-100"
          @click="mobileOpen = !mobileOpen"
          :aria-expanded="mobileOpen"
          aria-controls="mobile-menu"
          aria-label="Abrir ou fechar menu"
        >
          <svg class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
            <path v-if="!mobileOpen" stroke-linecap="round" stroke-linejoin="round" d="M4 6h16M4 12h16M4 18h16" />
            <path v-else stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>

      <!-- Mobile menu -->
      <div
        v-if="mobileOpen"
        id="mobile-menu"
        class="md:hidden mt-3 space-y-2 pb-3"
      >
        <router-link
          v-for="item in menuItems"
          :key="item.to"
          :to="item.to"
          :aria-label="item.label"
          class="block text-sm font-medium py-2"
          :class="route?.path === item.to ? 'text-primary-600' : 'text-gray-700 hover:text-primary-600'"
          :aria-current="route?.path === item.to ? 'page' : undefined"
        >
          {{ item.text }}
        </router-link>

        <button
          v-if="authStore.isAuthenticated"
          @click="handleLogout"
          class="block w-full text-left text-primary-600 font-medium text-sm py-2"
          aria-label="Sair da conta"
        >
          Sair
        </button>

        <router-link
          v-else
          to="/login"
          class="block text-primary-600 font-medium text-sm py-2"
          aria-label="Entrar"
        >
          Entrar
        </router-link>
      </div>
    </div>
  </nav>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const mobileOpen = ref(false)

const menuItems = computed(() => {
  const role = authStore.userRole?.toLowerCase()

  if (role === 'admin') {
    return [
      { to: '/dashboard', text: 'Dashboard', label: 'Dashboard' },
      { to: '/courses', text: 'Cursos', label: 'Cursos' },
      { to: '/classes', text: 'Turmas', label: 'Turmas' },
      { to: '/students', text: 'Alunos', label: 'Alunos' },
      { to: '/enrollments', text: 'Matrículas', label: 'Matrículas' },
      { to: '/payments', text: 'Pagamentos', label: 'Pagamentos' },
      { to: '/certificates', text: 'Certificados', label: 'Certificados' },
    ]
  }

  if (role === 'student') {
    return [
      { to: '/dashboard', text: 'Dashboard', label: 'Dashboard' },
      { to: '/catalog', text: 'Explorar cursos', label: 'Explorar cursos' },
      { to: '/certificates', text: 'Certificados', label: 'Certificados' },
    ]
  }

  return [
    { to: '/', text: 'Início', label: 'Página inicial' },
    { to: '/catalog', text: 'Cursos', label: 'Cursos' },
  ]
})

const handleLogout = () => {
  mobileOpen.value = false
  authStore.logout()
  router.push('/login')
}
</script>
