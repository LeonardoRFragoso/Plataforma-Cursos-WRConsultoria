<template>
  <div class="min-h-screen flex flex-col">
    <AppNavbar />

    <main class="flex-1 bg-gray-50 py-12">
      <div v-if="loading" class="text-center text-gray-500">Carregando curso...</div>

      <div v-else-if="error" class="max-w-3xl mx-auto px-4">
        <div class="bg-red-50 border border-red-200 text-red-700 p-4 rounded-md">
          {{ error }}
        </div>
      </div>

      <div v-else-if="course" class="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8">
        <div class="bg-white rounded-lg shadow-md border border-gray-200 overflow-hidden">
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
                    <span class="text-lg font-semibold text-secondary-900">{{ course.type }}</span>
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
                    Entrar para comprar
                  </button>

                  <button
                    v-else
                    :disabled="purchasing"
                    @click="startPurchase"
                    class="w-full py-3 px-4 bg-primary-600 text-white rounded-md hover:bg-primary-700 font-semibold transition-colors disabled:opacity-60"
                  >
                    {{ purchasing ? 'Redirecionando...' : 'Comprar agora' }}
                  </button>

                  <p v-if="purchaseError" class="mt-3 text-sm text-red-600 text-center">
                    {{ purchaseError }}
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

    <footer class="bg-primary-700 text-white/80 py-6">
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
import { fetchCourse } from '../api/courses'
import { purchaseCourse, createCheckout } from '../api/enrollments'
import AppNavbar from '../components/AppNavbar.vue'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const tenantStore = useTenantStore()

const course = ref(null)
const loading = ref(true)
const error = ref('')
const purchasing = ref(false)
const purchaseError = ref('')

const redirectPath = computed(() => route.fullPath)
const loginWithRedirect = computed(() => ({ path: '/login', query: { redirect: redirectPath.value } }))
const registerWithRedirect = computed(() => ({ path: '/register', query: { redirect: redirectPath.value } }))

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
    const { data } = await purchaseCourse(course.value.id, 'BOLETO')
    const paymentId = data.payment.id
    const checkout = await createCheckout(paymentId)
    window.location.href = checkout.data.checkout_url
  } catch (err) {
    purchaseError.value = err.response?.data?.detail || 'Erro ao iniciar a compra. Tente novamente.'
    purchasing.value = false
  }
}

onMounted(async () => {
  try {
    const { data } = await fetchCourse(route.params.id)
    course.value = data
  } catch (err) {
    error.value = err.response?.data?.detail || 'Curso não encontrado.'
  } finally {
    loading.value = false
  }
})
</script>
