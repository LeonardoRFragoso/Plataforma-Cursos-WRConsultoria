<template>
  <div class="min-h-screen flex flex-col">
    <!-- Header branco com logo -->
    <header class="bg-white shadow-md border-b border-gray-200">
      <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-3 flex justify-between items-center">
        <router-link :to="homeRoute" class="flex items-center" data-testid="home-logo">
          <img v-if="tenantStore.logo_url" :src="tenantStore.logo_url" :alt="tenantStore.name" class="h-12 w-auto" />
          <span v-else class="text-xl font-bold text-primary-600">{{ tenantName }}</span>
        </router-link>
        <!-- Desktop nav -->
        <nav class="hidden md:flex items-center space-x-4">
          <template v-if="authStore.isAuthenticated">
            <!-- Role-aware authenticated navigation -->
            <router-link
              v-for="link in authedLinks"
              :key="link.to"
              :to="link.to"
              class="text-gray-700 hover:text-primary-600 font-medium text-sm transition-colors"
              :data-testid="'home-nav-' + link.testid"
            >
              {{ link.label }}
            </router-link>
            <button
              @click="handleLogout"
              class="text-gray-500 hover:text-red-600 font-medium text-sm transition-colors"
              data-testid="home-nav-logout"
            >
              Sair
            </button>
          </template>
          <template v-else>
            <router-link to="/" class="text-gray-700 hover:text-primary-600 font-medium text-sm transition-colors" data-testid="home-nav-inicio">
              Início
            </router-link>
            <router-link to="/cursos" class="text-gray-700 hover:text-primary-600 font-medium text-sm transition-colors" data-testid="home-nav-cursos">
              Cursos
            </router-link>
            <router-link to="/validar-certificado" class="text-gray-700 hover:text-primary-600 font-medium text-sm transition-colors" data-testid="home-nav-validar">
              Validar certificado
            </router-link>
            <router-link to="/seja-parceiro" class="text-gray-700 hover:text-primary-600 font-medium text-sm transition-colors" data-testid="home-nav-parceiro">
              Seja parceiro
            </router-link>
            <router-link to="/login" class="text-gray-700 hover:text-primary-600 font-medium text-sm transition-colors" data-testid="home-nav-login">
              Login
            </router-link>
            <router-link
              to="/register"
              class="bg-primary-600 text-white px-5 py-2 rounded-md hover:bg-primary-700 font-semibold text-sm transition-colors"
              data-testid="home-nav-cadastro"
            >
              Cadastro
            </router-link>
          </template>
        </nav>
        <!-- Mobile hamburger -->
        <button
          @click="mobileMenuOpen = !mobileMenuOpen"
          class="md:hidden text-gray-700 hover:text-primary-600"
          data-testid="home-mobile-menu-toggle"
          :aria-expanded="mobileMenuOpen"
          aria-controls="home-mobile-menu"
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
        id="home-mobile-menu"
        class="md:hidden border-t border-gray-200 bg-white px-4 pb-4 space-y-1"
        data-testid="home-mobile-menu"
      >
        <template v-if="authStore.isAuthenticated">
          <router-link
            v-for="link in authedLinks"
            :key="link.to"
            :to="link.to"
            @click="mobileMenuOpen = false"
            class="block py-2 px-3 rounded-md text-gray-700 hover:text-primary-600 hover:bg-gray-50 font-medium text-sm"
            :data-testid="'home-mobile-nav-' + link.testid"
          >
            {{ link.label }}
          </router-link>
          <button
            @click="handleLogout"
            class="block w-full text-left py-2 px-3 rounded-md text-gray-500 hover:text-red-600 hover:bg-gray-50 font-medium text-sm"
            data-testid="home-mobile-nav-logout"
          >
            Sair
          </button>
        </template>
        <template v-else>
          <router-link to="/" @click="mobileMenuOpen = false" class="block py-2 px-3 rounded-md text-gray-700 hover:text-primary-600 hover:bg-gray-50 font-medium text-sm" data-testid="home-mobile-nav-inicio">
            Início
          </router-link>
          <router-link to="/cursos" @click="mobileMenuOpen = false" class="block py-2 px-3 rounded-md text-gray-700 hover:text-primary-600 hover:bg-gray-50 font-medium text-sm" data-testid="home-mobile-nav-cursos">
            Cursos
          </router-link>
          <router-link to="/validar-certificado" @click="mobileMenuOpen = false" class="block py-2 px-3 rounded-md text-gray-700 hover:text-primary-600 hover:bg-gray-50 font-medium text-sm" data-testid="home-mobile-nav-validar">
            Validar certificado
          </router-link>
          <router-link to="/seja-parceiro" @click="mobileMenuOpen = false" class="block py-2 px-3 rounded-md text-gray-700 hover:text-primary-600 hover:bg-gray-50 font-medium text-sm" data-testid="home-mobile-nav-parceiro">
            Seja parceiro
          </router-link>
          <router-link to="/login" @click="mobileMenuOpen = false" class="block py-2 px-3 rounded-md text-gray-700 hover:text-primary-600 hover:bg-gray-50 font-medium text-sm" data-testid="home-mobile-nav-login">
            Login
          </router-link>
          <router-link to="/register" @click="mobileMenuOpen = false" class="block py-2 px-3 rounded-md bg-primary-600 text-white hover:bg-primary-700 font-semibold text-sm" data-testid="home-mobile-nav-cadastro">
            Cadastro
          </router-link>
        </template>
      </div>
    </header>

    <!-- Hero Section -->
    <section class="relative overflow-hidden bg-primary-600 text-white" data-testid="home-hero">
      <!-- WR hero artwork (only rendered for WR tenant) -->
      <template v-if="wrHero">
        <!-- Desktop/tablet: full banner image with overlay CTA -->
        <div class="hidden sm:block relative">
          <img
            :src="wrHero.src"
            :alt="wrHero.alt"
            fetchpriority="high"
            width="1672"
            height="941"
            class="w-full h-auto object-cover"
            data-testid="home-hero-img"
          />
          <div class="absolute inset-0 bg-gradient-to-r from-black/60 via-black/20 to-transparent flex items-center">
            <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 w-full">
              <div class="max-w-lg">
                <h1 class="text-3xl sm:text-4xl font-bold mb-4 leading-tight drop-shadow-lg">
                  Treinamentos que preparam equipes para trabalhar com segurança
                </h1>
                <p class="text-base sm:text-lg text-white/90 mb-6 drop-shadow">
                  Plataforma de cursos da {{ tenantName }}.
                </p>
                <router-link
                  v-if="!authStore.isAuthenticated"
                  to="/register"
                  class="inline-block bg-white text-primary-600 px-6 py-3 rounded-md hover:bg-primary-50 transition-colors text-base font-semibold shadow-lg"
                >
                  Comece Agora
                </router-link>
                <router-link
                  v-else
                  :to="homeRoute"
                  class="inline-block bg-white text-primary-600 px-6 py-3 rounded-md hover:bg-primary-50 transition-colors text-base font-semibold shadow-lg"
                >
                  Ir para Dashboard
                </router-link>
              </div>
            </div>
          </div>
        </div>
        <!-- Mobile: HTML heading + CTA with hero image below (text in image too small on mobile) -->
        <div class="sm:hidden relative">
          <div class="px-4 py-10 text-center bg-gradient-to-br from-primary-900 via-primary-700 to-secondary-900">
            <h1 class="text-2xl font-bold mb-4 leading-tight">
              Treinamentos que preparam equipes para trabalhar com segurança
            </h1>
            <p class="text-sm text-white/90 mb-6">
              Plataforma de cursos da {{ tenantName }}.
            </p>
            <router-link
              v-if="!authStore.isAuthenticated"
              to="/register"
              class="inline-block bg-white text-primary-600 px-6 py-2.5 rounded-md hover:bg-primary-50 transition-colors text-sm font-semibold shadow-lg"
            >
              Comece Agora
            </router-link>
            <router-link
              v-else
              :to="homeRoute"
              class="inline-block bg-white text-primary-600 px-6 py-2.5 rounded-md hover:bg-primary-50 transition-colors text-sm font-semibold shadow-lg"
            >
              Ir para Dashboard
            </router-link>
          </div>
          <img
            :src="wrHero.src"
            :alt="wrHero.alt"
            loading="eager"
            width="1672"
            height="941"
            class="w-full h-auto object-cover"
            data-testid="home-hero-img-mobile"
          />
        </div>
      </template>
      <!-- Non-WR hero: gradient + text (no /assets/wr/ reference) -->
      <template v-else>
        <div class="absolute inset-0 bg-gradient-to-br from-primary-900 via-primary-700 to-secondary-900"></div>
        <div class="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-24 text-center">
          <h1 class="text-4xl sm:text-5xl font-bold mb-6 leading-tight">
            Cursos e certificações<br />com qualidade reconhecida
          </h1>
          <p class="text-lg sm:text-xl text-white/90 mb-10 max-w-2xl mx-auto">
            Plataforma de cursos da {{ tenantName }}.
          </p>
          <router-link
            v-if="!authStore.isAuthenticated"
            to="/register"
            class="inline-block bg-white text-primary-600 px-8 py-3 rounded-md hover:bg-primary-50 transition-colors text-lg font-semibold shadow-lg"
          >
            Comece Agora
          </router-link>
          <router-link
            v-else
            :to="homeRoute"
            class="inline-block bg-white text-primary-600 px-8 py-3 rounded-md hover:bg-primary-50 transition-colors text-lg font-semibold shadow-lg"
          >
            Ir para Dashboard
          </router-link>
        </div>
      </template>
    </section>

    <!-- Features -->
    <section class="flex-1 bg-gray-50 py-20">
      <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div class="text-center mb-16">
          <h2 class="text-3xl font-bold text-secondary-900 mb-4">Por que escolher a {{ tenantName }}?</h2>
          <p class="text-gray-600 max-w-2xl mx-auto">
            Cursos profissionais com conteúdo atualizado e certificação com verificação online.
          </p>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-3 gap-8">
          <!-- Cursos Variados -->
          <div class="bg-white p-8 rounded-lg shadow-md hover:shadow-lg transition-shadow border border-gray-200">
            <div class="w-12 h-12 bg-primary-50 rounded-lg flex items-center justify-center mb-5">
              <svg class="w-7 h-7 text-primary-600" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
                <path stroke-linecap="round" stroke-linejoin="round" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
              </svg>
            </div>
            <h3 class="text-xl font-semibold text-secondary-900 mb-2">Cursos Variados</h3>
            <p class="text-gray-600">Acesso a cursos com conteúdo atualizado e material didático completo, com aulas em vídeo e materiais de apoio.</p>
          </div>

          <!-- Certificação -->
          <div class="bg-white p-8 rounded-lg shadow-md hover:shadow-lg transition-shadow border border-gray-200">
            <div class="w-12 h-12 bg-primary-50 rounded-lg flex items-center justify-center mb-5">
              <svg class="w-7 h-7 text-primary-600" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
                <path stroke-linecap="round" stroke-linejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
            <h3 class="text-xl font-semibold text-secondary-900 mb-2">Certificação</h3>
            <p class="text-gray-600">Receba certificados com código de verificação após concluir todas as aulas do curso. Valide a autenticidade online.</p>
          </div>

          <!-- Plataforma Moderna -->
          <div class="bg-white p-8 rounded-lg shadow-md hover:shadow-lg transition-shadow border border-gray-200">
            <div class="w-12 h-12 bg-primary-50 rounded-lg flex items-center justify-center mb-5">
              <svg class="w-7 h-7 text-primary-600" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
                <path stroke-linecap="round" stroke-linejoin="round" d="M9 17.25v1.007a3 3 0 01-.879 2.122L7.5 21h9l-.621-.621A3 3 0 0115 18.257V17.25m6-12V15a2.25 2.25 0 01-2.25 2.25H5.25A2.25 2.25 0 013 15V5.25m18 0A2.25 2.25 0 0018.75 3H5.25A2.25 2.25 0 003 5.25m18 0V12a2.25 2.25 0 01-2.25 2.25H5.25A2.25 2.25 0 013 12V5.25" />
              </svg>
            </div>
            <h3 class="text-xl font-semibold text-secondary-900 mb-2">Plataforma Moderna</h3>
            <p class="text-gray-600">Acesso fácil e intuitivo de qualquer dispositivo. Cursos presenciais, EAD ou semipresenciais, conforme a turma.</p>
          </div>
        </div>
      </div>
    </section>

    <!-- Vitrine de Cursos -->
    <section class="py-20 bg-white" data-testid="home-featured-courses">
      <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div class="text-center mb-12">
          <h2 class="text-3xl font-bold text-secondary-900 mb-4">Cursos em destaque</h2>
          <p class="text-gray-600 max-w-2xl mx-auto">
            Escolha um curso e inicie sua jornada de capacitação.
          </p>
        </div>

        <div v-if="loading" class="text-center text-gray-500">Carregando cursos...</div>

        <div v-else-if="courses.length" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
          <div
            v-for="course in courses"
            :key="course.id"
            class="bg-white rounded-lg shadow-md hover:shadow-lg transition-shadow border border-gray-200 overflow-hidden flex flex-col"
          >
            <CourseCover
              :course="course"
              ratio="16/9"
              loading="lazy"
              :img-test-id="'home-course-cover-img'"
              :fb-test-id="'home-course-cover-fallback'"
            />
            <div class="p-6 flex-1">
              <h3 class="text-xl font-semibold text-secondary-900 mb-2">{{ course.name }}</h3>
              <p class="text-sm text-gray-500 mb-4 uppercase tracking-wide">{{ course.category }}</p>
              <p class="text-gray-600 text-sm mb-4 line-clamp-3">{{ course.description }}</p>
              <div class="flex items-center justify-between text-sm text-gray-600">
                <span>Carga: {{ course.carga_horaria }}h</span>
                <span class="font-semibold text-primary-600">{{ formatPrice(course.price) }}</span>
              </div>
            </div>
            <div class="p-4 border-t border-gray-100 bg-gray-50">
              <router-link
                :to="`/cursos/${course.id}`"
                class="block w-full text-center py-2 bg-primary-600 text-white rounded-md hover:bg-primary-700 font-semibold transition-colors"
              >
                Ver detalhes
              </router-link>
            </div>
          </div>
        </div>

        <div v-else class="text-center text-gray-500">
          Nenhum curso disponível no momento.
        </div>
      </div>
    </section>

    <!-- Footer -->
    <footer class="bg-primary-700 text-white/80 py-8">
      <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
        <img v-if="tenantStore.logo_url" :src="tenantStore.logo_url" :alt="tenantStore.name" class="h-10 w-auto mx-auto mb-4" />
        <p class="text-sm">{{ tenantName }} — Treinamentos com certificação</p>
        <p class="text-xs text-white/50 mt-2">&copy; {{ new Date().getFullYear() }} {{ tenantName }}. Todos os direitos reservados.</p>
      </div>
    </footer>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useTenantStore } from '../stores/tenant'
import { useAuthStore } from '../stores/auth'
import { fetchPublicCourses } from '../api/courses'
import { getHomeRoute } from '../utils/homeRoute'
import { getWrHero } from '../utils/courseMedia'
import CourseCover from '../components/CourseCover.vue'

const router = useRouter()
const tenantStore = useTenantStore()
const authStore = useAuthStore()
const courses = ref([])
const loading = ref(true)
const mobileMenuOpen = ref(false)
const tenantName = computed(() => tenantStore.name || 'Plataforma de Cursos')
const homeRoute = computed(() => getHomeRoute(authStore))
const wrHero = computed(() => getWrHero())

const authedLinks = computed(() => {
  const role = authStore.userRole?.toLowerCase()
  if (role === 'student') {
    return [
      { to: '/dashboard', label: 'Dashboard', testid: 'dashboard' },
      { to: '/cursos', label: 'Catálogo', testid: 'catalog' },
      { to: '/certificates', label: 'Certificados', testid: 'certificates' },
    ]
  }
  if (role === 'admin') {
    return [
      { to: '/dashboard', label: 'Dashboard', testid: 'dashboard' },
      { to: '/courses', label: 'Gestão', testid: 'management' },
    ]
  }
  if (role === 'super_admin') {
    return [
      { to: '/super-admin', label: 'Gestão Global', testid: 'super-admin' },
    ]
  }
  return []
})

const handleLogout = () => {
  authStore.logout()
  router.push('/login')
}

function formatPrice(price) {
  if (price === 0 || price === null) return 'Gratuito'
  return new Intl.NumberFormat('pt-BR', {
    style: 'currency',
    currency: 'BRL',
  }).format(price)
}

onMounted(async () => {
  try {
    const { data } = await fetchPublicCourses()
    courses.value = data
  } catch {
    courses.value = []
  } finally {
    loading.value = false
  }
})
</script>
