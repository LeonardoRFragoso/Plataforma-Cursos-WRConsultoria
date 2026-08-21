<template>
  <div class="min-h-screen flex flex-col">
    <!-- Header branco com logo -->
    <header class="bg-white shadow-md border-b border-gray-200">
      <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-3 flex justify-between items-center">
        <router-link :to="homeRoute" class="flex items-center" data-testid="home-logo">
          <img v-if="tenantStore.logo_url" :src="tenantStore.logo_url" :alt="tenantStore.name" class="h-12 w-auto" />
          <span
            v-else-if="tenantStore.loading && !tenantStore.loaded"
            class="text-sm text-gray-400"
            data-testid="home-brand-loading"
          >
            Carregando…
          </span>
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

    <!-- Hero Section.

         WR: the generated hero artwork already embeds the marketing headline,
         WR logo and people. We display it intact (no overlay headline, no
         aggressive darkening) and place the CTA in a clean action bar below
         the artwork so embedded typography stays legible. A visually-hidden
         h1 provides the accessible heading without duplicating visible text.

         Non-WR: neutral tenant-colored gradient + visible headline (no
         /assets/wr/ reference). -->
    <section class="bg-primary-900 text-white" data-testid="home-hero">
      <template v-if="wrHero">
        <!-- Desktop/tablet: full 16:9 artwork intact, CTA bar below -->
        <div class="hidden sm:block">
          <img
            :src="wrHero.src"
            :alt="wrHero.alt"
            fetchpriority="high"
            width="1672"
            height="941"
            class="block w-full h-auto object-cover"
            data-testid="home-hero-img"
          />
        </div>
        <!-- Mobile: controlled crop of the visual area (embedded text is not
             readable at 390px), then HTML headline + CTA below. -->
        <div class="sm:hidden">
          <img
            :src="wrHero.src"
            :alt="wrHero.alt"
            loading="eager"
            width="1672"
            height="941"
            class="block w-full object-cover"
            style="aspect-ratio: 4/3;"
            data-testid="home-hero-img-mobile"
          />
          <div class="px-4 py-8 text-center">
            <h1 class="text-2xl font-bold mb-3 leading-tight">
              Treinamentos que preparam equipes para trabalhar com segurança
            </h1>
            <p class="text-sm text-white/85 mb-5">
              Plataforma de cursos da {{ tenantName }}.
            </p>
            <router-link
              v-if="!authStore.isAuthenticated"
              to="/register"
              class="inline-block bg-white text-primary-700 px-6 py-2.5 rounded-md hover:bg-primary-50 transition-colors text-sm font-semibold shadow"
            >
              Comece Agora
            </router-link>
            <router-link
              v-else
              :to="homeRoute"
              class="inline-block bg-white text-primary-700 px-6 py-2.5 rounded-md hover:bg-primary-50 transition-colors text-sm font-semibold shadow"
            >
              Ir para Dashboard
            </router-link>
          </div>
        </div>
        <!-- Desktop CTA action bar (below artwork) -->
        <div class="hidden sm:block px-6 lg:px-8 py-6 text-center">
          <p class="text-base text-white/90 mb-3">Explore nossos treinamentos profissionais.</p>
          <router-link
            v-if="!authStore.isAuthenticated"
            to="/cursos"
            class="inline-block bg-white text-primary-700 px-7 py-3 rounded-md hover:bg-primary-50 transition-colors text-base font-semibold shadow"
            data-testid="home-hero-cta"
          >
            Ver cursos
          </router-link>
          <router-link
            v-else
            :to="homeRoute"
            class="inline-block bg-white text-primary-700 px-7 py-3 rounded-md hover:bg-primary-50 transition-colors text-base font-semibold shadow"
            data-testid="home-hero-cta"
          >
            Ir para Dashboard
          </router-link>
        </div>
        <!-- Accessible heading for desktop (visually hidden — the artwork
             already conveys the marketing headline visually). -->
        <h1 class="sr-only">Treinamentos que preparam equipes para trabalhar com segurança — {{ tenantName }}</h1>
      </template>
      <!-- Non-WR hero: gradient + visible text (no /assets/wr/ reference) -->
      <template v-else>
        <div class="relative overflow-hidden">
          <div class="absolute inset-0 bg-gradient-to-br from-primary-900 via-primary-700 to-secondary-900"></div>
          <div class="relative max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-24 text-center">
            <h1 class="text-4xl sm:text-5xl font-bold mb-6 leading-tight">
              Cursos e certificações<br />com qualidade reconhecida
            </h1>
            <p class="text-lg sm:text-xl text-white/90 mb-10 max-w-2xl mx-auto">
              Plataforma de cursos da {{ tenantName }}.
            </p>
            <router-link
              v-if="!authStore.isAuthenticated"
              to="/register"
              class="inline-block bg-white text-primary-700 px-8 py-3 rounded-md hover:bg-primary-50 transition-colors text-lg font-semibold shadow-lg"
            >
              Comece Agora
            </router-link>
            <router-link
              v-else
              :to="homeRoute"
              class="inline-block bg-white text-primary-700 px-8 py-3 rounded-md hover:bg-primary-50 transition-colors text-lg font-semibold shadow-lg"
            >
              Ir para Dashboard
            </router-link>
          </div>
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

    <!-- Vitrine de Cursos — distinguishes LOADING / ERROR / EMPTY / SUCCESS.

         Only a small featured subset is rendered so we don't load every
         course cover image on the Home page. -->
    <section class="py-20 bg-white" data-testid="home-featured-courses">
      <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div class="text-center mb-12">
          <h2 class="text-3xl font-bold text-secondary-900 mb-4">Cursos em destaque</h2>
          <p class="text-gray-600 max-w-2xl mx-auto">
            Escolha um curso e inicie sua jornada de capacitação.
          </p>
        </div>

        <!-- LOADING: skeleton cards (no fake course data) -->
        <div
          v-if="loading"
          class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8"
          data-testid="home-featured-loading"
          aria-busy="true"
        >
          <div
            v-for="n in 3"
            :key="n"
            class="bg-white rounded-lg shadow-md border border-gray-200 overflow-hidden"
          >
            <div class="aspect-video bg-gray-200 animate-pulse"></div>
            <div class="p-6 space-y-3">
              <div class="h-5 bg-gray-200 rounded animate-pulse w-1/3"></div>
              <div class="h-6 bg-gray-200 rounded animate-pulse w-3/4"></div>
              <div class="h-4 bg-gray-200 rounded animate-pulse w-1/2"></div>
            </div>
          </div>
        </div>

        <!-- ERROR: clear retry state, never shown as "empty" -->
        <div
          v-else-if="loadError"
          class="max-w-md mx-auto text-center bg-red-50 border border-red-200 rounded-lg p-8"
          data-testid="home-featured-error"
        >
          <svg class="w-10 h-10 mx-auto mb-3 text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M12 9v2m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <p class="text-red-700 font-medium mb-1">Não foi possível carregar os cursos.</p>
          <p class="text-sm text-red-600 mb-4">Verifique sua conexão e tente novamente.</p>
          <button
            @click="loadCourses"
            class="px-5 py-2 bg-primary-600 text-white rounded-md hover:bg-primary-700 font-semibold text-sm transition-colors"
          >
            Tentar novamente
          </button>
        </div>

        <!-- SUCCESS: real API course cards with complete cover artwork -->
        <div
          v-else-if="courses.length"
          class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8"
          data-testid="home-featured-success"
        >
          <div
            v-for="course in courses"
            :key="course.id"
            class="bg-white rounded-lg shadow-md hover:shadow-lg transition-shadow border border-gray-200 overflow-hidden flex flex-col"
          >
            <CourseCover
              :course="course"
              ratio="16/9"
              fit="contain"
              loading="lazy"
              :img-test-id="'home-course-cover-img'"
              :fb-test-id="'home-course-cover-fallback'"
            />
            <div class="p-6 flex-1 flex flex-col">
              <p class="text-xs font-semibold text-primary-600 uppercase tracking-wide mb-1">{{ course.code }}</p>
              <h3 class="text-lg font-semibold text-secondary-900 mb-2">{{ course.name }}</h3>
              <p class="text-sm text-gray-500 mb-4">{{ course.category }}</p>
              <div class="mt-auto flex items-center justify-between text-sm text-gray-600 pt-3 border-t border-gray-100">
                <span>{{ course.carga_horaria }}h · {{ formatModality(course.modality) }}</span>
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

        <!-- TRUE EMPTY: intentional compact state -->
        <div
          v-else
          class="max-w-md mx-auto text-center bg-gray-50 border border-gray-200 rounded-lg p-8"
          data-testid="home-featured-empty"
        >
          <svg class="w-10 h-10 mx-auto mb-3 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
          </svg>
          <p class="text-gray-700 font-medium mb-1">Nenhum curso disponível no momento.</p>
          <p class="text-sm text-gray-500">Novos treinamentos serão disponibilizados em breve.</p>
        </div>

        <!-- CTA to full catalog -->
        <div
          v-if="courses.length && !loading && !loadError"
          class="text-center mt-12"
          data-testid="home-featured-cta"
        >
          <router-link
            to="/cursos"
            class="inline-block px-7 py-3 bg-primary-600 text-white rounded-md hover:bg-primary-700 font-semibold text-base transition-colors shadow"
          >
            Ver todos os cursos
          </router-link>
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
const loadError = ref('')
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

function formatModality(modality) {
  const map = {
    PRESENCIAL: 'Presencial',
    EAD: 'EAD',
    SEMIPRESENCIAL: 'Semipresencial',
  }
  return map[modality] || modality || ''
}

// Featured subset only — Home must not load every course cover image.
const FEATURED_LIMIT = 6

async function loadCourses() {
  loading.value = true
  loadError.value = ''
  try {
    const { data } = await fetchPublicCourses()
    // Distinguish a real empty catalog from an API failure: a successful
    // response (even an empty array) clears the error; only a thrown error
    // sets the error state.
    courses.value = Array.isArray(data) ? data.slice(0, FEATURED_LIMIT) : []
  } catch (error) {
    courses.value = []
    loadError.value = error.response?.data?.detail || 'Erro ao carregar cursos.'
  } finally {
    loading.value = false
  }
}

onMounted(loadCourses)
</script>
