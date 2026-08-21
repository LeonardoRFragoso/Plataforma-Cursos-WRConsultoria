<template>
  <div :class="isAuthenticatedStudent ? '' : 'min-h-screen flex flex-col'">
    <AppNavbar v-if="!isAuthenticatedStudent" />

    <!-- Catalog header — simpler than Home hero, tenant-tinted -->
    <section class="bg-gradient-to-br from-primary-900 via-primary-800 to-secondary-900 text-white py-16" data-testid="catalog-header">
      <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
        <h1 class="text-3xl sm:text-4xl font-bold mb-4">Cursos e Treinamentos</h1>
        <p class="text-lg text-white/85 max-w-2xl mx-auto">
          Capacitação profissional em segurança, saúde, qualidade e desenvolvimento.
        </p>
      </div>
    </section>

    <!-- Filters + course grid -->
    <main class="flex-1 bg-gray-50 py-12">
      <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <!-- Filter bar -->
        <div class="mb-8 flex flex-col sm:flex-row gap-4 items-start sm:items-center justify-between" data-testid="catalog-filters">
          <!-- Category tabs -->
          <div class="flex flex-wrap gap-2">
            <button
              v-for="cat in categories"
              :key="cat.key"
              @click="activeCategory = cat.key"
              :class="[
                'px-4 py-2 rounded-lg text-sm font-medium transition-colors',
                activeCategory === cat.key
                  ? 'bg-primary-600 text-white'
                  : 'bg-white text-gray-700 border border-gray-200 hover:border-primary-300 hover:text-primary-600'
              ]"
              :data-testid="'catalog-filter-' + cat.key"
            >
              {{ cat.label }}
            </button>
          </div>
          <!-- Search -->
          <div class="relative w-full sm:w-64">
            <input
              v-model="searchQuery"
              type="text"
              placeholder="Buscar curso..."
              class="w-full pl-10 pr-4 py-2 border border-gray-200 rounded-lg bg-white text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
              data-testid="catalog-search"
            />
            <svg class="absolute left-3 top-2.5 w-5 h-5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
          </div>
        </div>

        <!-- Result count -->
        <p class="text-sm text-gray-500 mb-6" data-testid="catalog-count">
          {{ filteredCourses.length }} curso{{ filteredCourses.length !== 1 ? 's' : '' }} disponíve{{ filteredCourses.length !== 1 ? 'is' : 'l' }}
        </p>

        <!-- LOADING -->
        <div
          v-if="loading"
          class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6"
          data-testid="catalog-loading"
          aria-busy="true"
        >
          <div
            v-for="n in 8"
            :key="n"
            class="bg-white rounded-lg shadow-md border border-gray-200 overflow-hidden"
          >
            <div class="aspect-video bg-gray-200 animate-pulse"></div>
            <div class="p-5 space-y-3">
              <div class="h-4 bg-gray-200 rounded animate-pulse w-1/3"></div>
              <div class="h-5 bg-gray-200 rounded animate-pulse w-3/4"></div>
              <div class="h-4 bg-gray-200 rounded animate-pulse w-1/2"></div>
            </div>
          </div>
        </div>

        <!-- ERROR -->
        <div
          v-else-if="loadError"
          class="max-w-md mx-auto text-center bg-red-50 border border-red-200 rounded-lg p-8"
          data-testid="catalog-error"
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

        <!-- SUCCESS: filtered course grid -->
        <div
          v-else-if="filteredCourses.length"
          class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6"
          data-testid="catalog-grid"
        >
          <div
            v-for="course in filteredCourses"
            :key="course.id"
            class="bg-white rounded-lg shadow-md hover:shadow-lg transition-shadow border border-gray-200 overflow-hidden flex flex-col"
          >
            <CourseCover
              :course="course"
              ratio="16/9"
              fit="contain"
              loading="lazy"
              :img-test-id="'catalog-cover-img'"
              :fb-test-id="'catalog-cover-fallback'"
            />
            <div class="p-5 flex-1 flex flex-col">
              <p class="text-xs font-semibold text-primary-600 uppercase tracking-wide mb-1">{{ course.code }}</p>
              <h3 class="text-base font-semibold text-secondary-900 mb-1 line-clamp-2">{{ course.name }}</h3>
              <p class="text-sm text-gray-500 mb-3">{{ course.category }}</p>
              <div class="mt-auto flex items-center justify-between text-sm text-gray-600 pt-3 border-t border-gray-100">
                <span>{{ course.carga_horaria }}h · {{ formatModality(course.modality) }}</span>
                <span class="font-semibold text-primary-600">{{ formatPrice(course.price) }}</span>
              </div>
            </div>
            <div class="p-3 border-t border-gray-100 bg-gray-50">
              <router-link
                :to="`/cursos/${course.id}`"
                class="block w-full text-center py-2 bg-primary-600 text-white rounded-md hover:bg-primary-700 font-semibold text-sm transition-colors"
              >
                Ver detalhes
              </router-link>
            </div>
          </div>
        </div>

        <!-- EMPTY (no filter results) -->
        <div
          v-else
          class="max-w-md mx-auto text-center bg-gray-50 border border-gray-200 rounded-lg p-8"
          data-testid="catalog-empty"
        >
          <svg class="w-10 h-10 mx-auto mb-3 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
          <p class="text-gray-700 font-medium mb-1">Nenhum curso encontrado.</p>
          <p class="text-sm text-gray-500">Tente ajustar os filtros ou a busca.</p>
        </div>
      </div>
    </main>

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
import { useTenantStore } from '../stores/tenant'
import { useAuthStore } from '../stores/auth'
import { fetchPublicCourses } from '../api/courses'
import AppNavbar from '../components/AppNavbar.vue'
import CourseCover from '../components/CourseCover.vue'

const tenantStore = useTenantStore()
const authStore = useAuthStore()

const isAuthenticatedStudent = computed(
  () => authStore.isAuthenticated && authStore.userRole?.toLowerCase() === 'student'
)
const tenantName = computed(() => tenantStore.name || 'Plataforma de Cursos')

const allCourses = ref([])
const loading = ref(true)
const loadError = ref('')
const activeCategory = ref('all')
const searchQuery = ref('')

const categories = computed(() => {
  const cats = [{ key: 'all', label: 'Todos' }]
  const seen = new Set()
  for (const c of allCourses.value) {
    const cat = c.category
    if (cat && !seen.has(cat)) {
      seen.add(cat)
      cats.push({ key: cat, label: cat })
    }
  }
  return cats
})

const filteredCourses = computed(() => {
  let result = allCourses.value
  if (activeCategory.value !== 'all') {
    result = result.filter((c) => c.category === activeCategory.value)
  }
  if (searchQuery.value.trim()) {
    const q = searchQuery.value.toLowerCase().trim()
    result = result.filter(
      (c) =>
        (c.name || '').toLowerCase().includes(q) ||
        (c.code || '').toLowerCase().includes(q) ||
        (c.category || '').toLowerCase().includes(q)
    )
  }
  return result
})

function formatPrice(price) {
  if (price === 0 || price === null) return 'Gratuito'
  return new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(price)
}

function formatModality(modality) {
  const map = { PRESENCIAL: 'Presencial', EAD: 'EAD', SEMIPRESENCIAL: 'Semipresencial' }
  return map[modality] || modality || ''
}

async function loadCourses() {
  loading.value = true
  loadError.value = ''
  try {
    const { data } = await fetchPublicCourses()
    allCourses.value = Array.isArray(data) ? data : []
  } catch (error) {
    allCourses.value = []
    loadError.value = error.response?.data?.detail || 'Erro ao carregar cursos.'
  } finally {
    loading.value = false
  }
}

onMounted(loadCourses)
</script>
