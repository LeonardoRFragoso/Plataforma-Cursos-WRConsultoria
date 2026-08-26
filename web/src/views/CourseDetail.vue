<template>
  <div :class="isAuthenticatedStudent ? '' : 'min-h-screen flex flex-col'">
    <AppNavbar v-if="!isAuthenticatedStudent" />

    <main class="flex-1 bg-gray-50 py-12">
      <div v-if="loading" class="text-center text-gray-500">Carregando curso...</div>

      <div v-else-if="error" class="max-w-3xl mx-auto px-4">
        <div class="bg-red-50 border border-red-200 text-red-700 p-4 rounded-md">
          {{ error }}
        </div>
      </div>

      <div v-else-if="course" class="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8">
        <nav class="mb-4 text-sm text-gray-500" aria-label="Breadcrumb">
          <router-link to="/cursos" class="hover:text-primary-600">Catálogo</router-link>
          <span class="mx-2">/</span>
          <span class="text-gray-700">{{ course.category }}</span>
        </nav>

        <div class="bg-white rounded-lg shadow-md border border-gray-200 overflow-hidden">
          <CourseCover
            :course="course"
            ratio="16/9"
            fit="contain"
            loading="eager"
            img-test-id="course-detail-cover-img"
            fb-test-id="course-detail-cover-fallback"
          />

          <div class="p-8 md:p-12">
            <div class="flex flex-col md:flex-row md:items-start md:justify-between gap-8">
              <div class="flex-1">
                <p class="text-sm text-primary-600 font-semibold uppercase tracking-wide mb-2">{{ course.category }}</p>
                <h1 class="text-3xl md:text-4xl font-bold text-secondary-900 mb-4">{{ course.name }}</h1>
                <p class="text-gray-600 text-lg mb-6">{{ course.description }}</p>

                <div class="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-8">
                  <div class="bg-gray-50 p-4 rounded-lg border border-gray-200">
                    <span class="block text-xs text-gray-500 uppercase tracking-wide">Carga horária</span>
                    <span class="text-lg font-semibold text-secondary-900">{{ course.carga_horaria }}h</span>
                  </div>
                  <div class="bg-gray-50 p-4 rounded-lg border border-gray-200">
                    <span class="block text-xs text-gray-500 uppercase tracking-wide">Modalidade</span>
                    <span class="text-lg font-semibold text-secondary-900">{{ course.modality }}</span>
                  </div>
                  <div class="bg-gray-50 p-4 rounded-lg border border-gray-200">
                    <span class="block text-xs text-gray-500 uppercase tracking-wide">Tipo</span>
                    <span class="text-lg font-semibold text-secondary-900">{{ course.type || 'Formação' }}</span>
                  </div>
                  <div class="bg-gray-50 p-4 rounded-lg border border-gray-200">
                    <span class="block text-xs text-gray-500 uppercase tracking-wide">Código</span>
                    <span class="text-lg font-semibold text-secondary-900">{{ course.code }}</span>
                  </div>
                </div>

                <div v-if="course.prerequisite" class="mb-8">
                  <h3 class="text-lg font-semibold text-secondary-900 mb-2">Pré-requisitos</h3>
                  <p class="text-gray-600">{{ course.prerequisite }}</p>
                </div>

                <!-- Enriched content from apostila (CourseContentProfile) -->
                <div v-if="contentProfile" class="space-y-6 mb-8">
                  <div v-if="contentProfile.target_audience && contentProfile.target_audience !== 'REVIEW_REQUIRED'">
                    <h3 class="text-lg font-semibold text-secondary-900 mb-2">Público-alvo</h3>
                    <p class="text-gray-600">{{ contentProfile.target_audience }}</p>
                  </div>

                  <div v-if="contentProfile.general_objective">
                    <h3 class="text-lg font-semibold text-secondary-900 mb-2">Objetivo geral</h3>
                    <p class="text-gray-600">{{ contentProfile.general_objective }}</p>
                  </div>

                  <div v-if="contentProfile.specific_objectives && contentProfile.specific_objectives.length">
                    <h3 class="text-lg font-semibold text-secondary-900 mb-2">Objetivos específicos</h3>
                    <ul class="list-disc list-inside text-gray-600 space-y-1">
                      <li v-for="obj in contentProfile.specific_objectives" :key="obj">{{ obj }}</li>
                    </ul>
                  </div>

                  <div v-if="contentProfile.syllabus && contentProfile.syllabus.length">
                    <h3 class="text-lg font-semibold text-secondary-900 mb-2">Conteúdo programático</h3>
                    <ul class="list-disc list-inside text-gray-600 space-y-1">
                      <li v-for="topic in contentProfile.syllabus" :key="topic">{{ topic }}</li>
                    </ul>
                  </div>

                  <div v-if="contentProfile.key_topics && contentProfile.key_topics.length">
                    <h3 class="text-lg font-semibold text-secondary-900 mb-2">Principais tópicos</h3>
                    <ul class="list-disc list-inside text-gray-600 space-y-1">
                      <li v-for="topic in contentProfile.key_topics" :key="topic">{{ topic }}</li>
                    </ul>
                  </div>

                  <div v-if="contentProfile.risks_covered && contentProfile.risks_covered.length">
                    <h3 class="text-lg font-semibold text-secondary-900 mb-2">Riscos tratados</h3>
                    <ul class="list-disc list-inside text-gray-600 space-y-1">
                      <li v-for="risk in contentProfile.risks_covered" :key="risk">{{ risk }}</li>
                    </ul>
                  </div>

                  <div v-if="contentProfile.standards_referenced && contentProfile.standards_referenced.length">
                    <h3 class="text-lg font-semibold text-secondary-900 mb-2">Normas e referências</h3>
                    <ul class="list-disc list-inside text-gray-600 space-y-1">
                      <li v-for="std in contentProfile.standards_referenced" :key="std">{{ std }}</li>
                    </ul>
                  </div>

                  <div v-if="contentProfile.recycling_summary">
                    <h3 class="text-lg font-semibold text-secondary-900 mb-2">Reciclagem / Validade</h3>
                    <p class="text-gray-600">{{ contentProfile.recycling_summary }}</p>
                  </div>
                </div>

                <!-- Course materials (apostilas) -->
                <div v-if="materials && materials.length" class="mb-8">
                  <h3 class="text-lg font-semibold text-secondary-900 mb-3">Materiais do curso</h3>
                  <div class="space-y-2">
                    <div
                      v-for="material in materials"
                      :key="material.id"
                      class="flex items-center justify-between p-3 bg-gray-50 rounded-lg border border-gray-200"
                    >
                      <div class="flex items-center gap-3">
                        <svg class="w-5 h-5 text-primary-600" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
                          <path stroke-linecap="round" stroke-linejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                        </svg>
                        <span class="text-sm font-medium text-gray-700">{{ material.title }}</span>
                      </div>
                      <button
                        @click="downloadMaterial(material)"
                        class="text-sm font-semibold text-primary-600 hover:text-primary-700"
                      >
                        Visualizar / Baixar
                      </button>
                    </div>
                  </div>
                </div>
              </div>

              <div class="w-full md:w-80 shrink-0">
                <div class="bg-gray-50 p-6 rounded-lg border border-gray-200 sticky top-6">
                  <p class="text-3xl font-bold text-primary-600 mb-2">{{ formatPrice(course.price) }}</p>
                  <p class="text-sm text-gray-500 mb-6">{{ course.carga_horaria }}h de conteúdo</p>

                  <button
                    v-if="!authStore.isAuthenticated"
                    @click="goToLogin"
                    class="w-full py-3 px-4 bg-primary-600 text-white rounded-md hover:bg-primary-700 font-semibold transition-colors"
                  >
                    {{ Number(course.price || 0) <= 0 ? 'Entrar para começar' : 'Entrar para comprar' }}
                  </button>

                  <div v-else-if="enrollmentLoading" class="text-center text-gray-500 py-3">
                    Carregando matrícula...
                  </div>

                  <router-link
                    v-else-if="courseEnrollment?.status === 'CONFIRMADA' || courseEnrollment?.status === 'CONCLUIDA'"
                    :to="`/courses/${course.id}/learn`"
                    class="block w-full py-3 px-4 bg-green-600 text-white text-center rounded-md hover:bg-green-700 font-semibold transition-colors"
                  >
                    Acessar curso
                  </router-link>

                  <button
                    v-else
                    :disabled="purchasing"
                    @click="startPurchase"
                    class="w-full py-3 px-4 bg-primary-600 text-white rounded-md hover:bg-primary-700 font-semibold transition-colors disabled:opacity-60"
                  >
                    {{ purchasing ? purchaseLoadingText : purchaseButtonText }}
                  </button>

                  <p v-if="purchaseError" class="mt-3 text-sm text-red-600 text-center">
                    {{ purchaseError }}
                  </p>

                  <p v-if="course.price > 0 && !courseEnrollment" class="text-xs text-gray-400 mt-3 text-center">
                    Pagamento seguro via Pix, boleto ou cartão
                  </p>
                  <p v-else-if="Number(course.price || 0) <= 0 && !courseEnrollment" class="text-xs text-green-600 mt-3 text-center font-medium">
                    Acesso liberado sem pagamento
                  </p>

                  <p v-if="!authStore.isAuthenticated" class="text-sm text-gray-500 mt-4 text-center">
                    Já tem conta?
                    <router-link :to="loginWithRedirect" class="text-primary-600 hover:underline">Entre</router-link>
                    ou
                    <router-link :to="registerWithRedirect" class="text-primary-600 hover:underline">cadastre-se</router-link>
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </main>

    <footer v-if="!isAuthenticatedStudent" class="bg-primary-700 text-white/80 py-6">
      <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 text-center text-sm">
        {{ tenantStore.name || 'Plataforma de Cursos' }}
      </div>
    </footer>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { useTenantStore } from '../stores/tenant'
import { fetchCourse, fetchCourseContentProfile, fetchCourseMaterials, downloadCourseMaterial } from '../api/courses'
import { purchaseCourse, getMyEnrollments, createCheckout } from '../api/enrollments'
import AppNavbar from '../components/AppNavbar.vue'
import CourseCover from '../components/CourseCover.vue'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const tenantStore = useTenantStore()

const isAuthenticatedStudent = computed(
  () => authStore.isAuthenticated && authStore.userRole?.toLowerCase() === 'student'
)

const course = ref(null)
const loading = ref(true)
const error = ref('')
const purchasing = ref(false)
const purchaseError = ref('')
const enrollments = ref([])
const enrollmentLoading = ref(false)
const contentProfile = ref(null)
const materials = ref([])

const redirectPath = computed(() => route.fullPath)
const loginWithRedirect = computed(() => ({ path: '/login', query: { redirect: redirectPath.value } }))
const registerWithRedirect = computed(() => ({ path: '/register', query: { redirect: redirectPath.value } }))
const courseEnrollment = computed(() => enrollments.value.find((e) => e.course_id === course.value?.id))

function formatPrice(price) {
  if (price === 0 || price === null) return 'Gratuito'
  return new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(price)
}

function goToLogin() {
  router.push({ path: '/login', query: { redirect: redirectPath.value } })
}

async function startPurchase() {
  purchaseError.value = ''
  purchasing.value = true

  try {
    const { data } = await purchaseCourse(course.value.id, 'UNDEFINED')
    if (!data.payment) {
      await router.push(`/courses/${course.value.id}/learn`)
      return
    }
    const checkout = await createCheckout(data.payment.id)
    window.location.href = checkout.data.checkout_url
  } catch (err) {
    purchaseError.value = err.response?.data?.detail || 'Erro ao iniciar a compra. Tente novamente.'
    purchasing.value = false
  }
}

const purchaseButtonText = computed(() => {
  if (Number(course.value?.price || 0) <= 0) return 'Começar curso grátis'
  if (courseEnrollment.value?.status === 'PENDENTE') return 'Finalizar pagamento'
  if (courseEnrollment.value?.status === 'CANCELADA') return 'Comprar novamente'
  return 'Comprar agora'
})

const purchaseLoadingText = computed(() =>
  Number(course.value?.price || 0) <= 0 ? 'Liberando acesso...' : 'Redirecionando...'
)

async function downloadMaterial(material) {
  try {
    const { data } = await downloadCourseMaterial(course.value.id, material.id)
    if (data.download_url) {
      window.open(data.download_url, '_blank')
    }
  } catch (err) {
    // If not authorized, redirect to login
    if (err.response?.status === 401) {
      router.push({ path: '/login', query: { redirect: route.fullPath } })
    }
  }
}

onMounted(async () => {
  try {
    await authStore.initializeUser()
    const { data } = await fetchCourse(route.params.id)
    course.value = data

    // Load content profile (public, may 404 if not yet created)
    try {
      const { data: profile } = await fetchCourseContentProfile(route.params.id)
      contentProfile.value = profile
    } catch {
      // Content profile not yet available — silently skip
    }

    // Load materials (requires auth + enrollment)
    if (authStore.isAuthenticated) {
      enrollmentLoading.value = true
      const { data: list } = await getMyEnrollments()
      enrollments.value = list

      // Try to load materials (may 403 if not enrolled)
      try {
        const { data: mats } = await fetchCourseMaterials(route.params.id)
        materials.value = mats
      } catch {
        // Not enrolled or not authorized — materials stay empty
      }
    }
  } catch (err) {
    error.value = err.response?.data?.detail || 'Curso não encontrado.'
  } finally {
    loading.value = false
    enrollmentLoading.value = false
  }
})
</script>
