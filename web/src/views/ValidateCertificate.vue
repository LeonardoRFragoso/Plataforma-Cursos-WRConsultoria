<template>
  <div class="min-h-screen flex flex-col">
    <AppNavbar />

    <!-- Certificate validation — trust/certificate visual language.
         No photograph. Uses iconography, tenant gradient and a clean
         centered composition. -->
    <main class="flex-1 bg-gradient-to-br from-gray-50 via-primary-50/30 to-gray-50 py-16 lg:py-20" data-testid="validate-main">
      <div class="max-w-2xl mx-auto px-4 sm:px-6 lg:px-8">
        <!-- Header with shield/check motif -->
        <div class="text-center mb-10" data-testid="validate-header">
          <div class="mx-auto w-20 h-20 bg-primary-100 rounded-2xl flex items-center justify-center mb-6 shadow-sm">
            <svg class="w-11 h-11 text-primary-600" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.5">
              <path stroke-linecap="round" stroke-linejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              <path stroke-linecap="round" stroke-linejoin="round" d="M12 2.25l8.25 3v6c0 4.97-3.69 8.97-8.25 10.5C7.44 20.22 3.75 16.22 3.75 11.25v-6l8.25-3z" />
            </svg>
          </div>
          <h1 class="text-3xl sm:text-4xl font-bold text-secondary-900 mb-3">Validar certificado</h1>
          <p class="text-lg text-gray-600 max-w-xl mx-auto">
            Confirme a autenticidade de um certificado emitido pela plataforma.
          </p>
        </div>

        <!-- Validation card -->
        <div class="bg-white rounded-xl shadow-lg border border-gray-200 p-8 lg:p-10" data-testid="validate-card">
          <form class="space-y-5" @submit.prevent="handleSubmit">
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1.5">Código de validação</label>
              <input
                v-model="code"
                type="text"
                required
                placeholder="Cole o código de validação aqui"
                class="w-full p-3.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 text-base"
                data-testid="validate-code-input"
              />
            </div>
            <button
              type="submit"
              :disabled="loading"
              class="w-full py-3.5 bg-primary-600 text-white font-semibold rounded-lg hover:bg-primary-700 transition disabled:opacity-50 text-base"
              data-testid="validate-submit-btn"
            >
              {{ loading ? 'Verificando...' : 'Verificar certificado' }}
            </button>
          </form>

          <!-- Loading state -->
          <div v-if="loading" class="mt-8 text-center" data-testid="validate-loading">
            <svg class="animate-spin w-8 h-8 mx-auto text-primary-600" fill="none" viewBox="0 0 24 24">
              <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
              <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
            <p class="text-sm text-gray-500 mt-3">Verificando...</p>
          </div>

          <!-- Server/network error -->
          <AppAlert v-else-if="serverError" type="error" data-testid="validate-server-error">
            {{ serverError }}
          </AppAlert>

          <!-- Valid certificate — strong visual result -->
          <div
            v-else-if="result && result.valid"
            class="mt-8 p-6 rounded-xl bg-green-50 border-2 border-green-200"
            data-testid="validate-valid"
          >
            <div class="flex items-center gap-3 mb-5">
              <div class="flex-shrink-0 w-12 h-12 bg-green-500 rounded-full flex items-center justify-center">
                <svg class="w-7 h-7 text-white" fill="currentColor" viewBox="0 0 20 20">
                  <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd" />
                </svg>
              </div>
              <div>
                <p class="text-lg font-bold text-green-800">{{ result.is_demo ? 'Certificado de demonstração' : 'Certificado válido' }}</p>
                <p class="text-sm text-green-600">{{ result.is_demo ? 'SEM VALIDADE OFICIAL — ambiente de homologação' : 'Autenticidade confirmada' }}</p>
              </div>
            </div>
            <div class="space-y-3 text-sm bg-white rounded-lg p-4 border border-green-100">
              <div class="flex justify-between">
                <span class="text-gray-500">Número</span>
                <span class="font-semibold text-gray-900">{{ result.certificate_number }}</span>
              </div>
              <div class="flex justify-between">
                <span class="text-gray-500">Aluno</span>
                <span class="font-semibold text-gray-900">{{ result.student_name }}</span>
              </div>
              <div class="flex justify-between">
                <span class="text-gray-500">Curso</span>
                <span class="font-semibold text-gray-900 text-right">{{ result.course_name }}</span>
              </div>
              <div class="flex justify-between">
                <span class="text-gray-500">Emitido em</span>
                <span class="font-semibold text-gray-900">{{ formatDate(result.issued_at) }}</span>
              </div>
            </div>
          </div>

          <!-- Invalid/not found — clear error state -->
          <div
            v-else-if="result && !result.valid"
            class="mt-8 p-6 rounded-xl bg-red-50 border-2 border-red-200"
            data-testid="validate-invalid"
          >
            <div class="flex items-center gap-3 mb-2">
              <div class="flex-shrink-0 w-12 h-12 bg-red-500 rounded-full flex items-center justify-center">
                <svg class="w-7 h-7 text-white" fill="currentColor" viewBox="0 0 20 20">
                  <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clip-rule="evenodd" />
                </svg>
              </div>
              <div>
                <p class="text-lg font-bold text-red-800">Código não encontrado</p>
                <p class="text-sm text-red-600">Verificação sem resultado</p>
              </div>
            </div>
            <p class="text-sm text-red-700 mt-3">O certificado não foi localizado em nossa base de dados. Confira o código e tente novamente.</p>
          </div>
        </div>

        <!-- Capabilities — only what validation actually returns -->
        <div class="mt-8 grid grid-cols-1 sm:grid-cols-3 gap-4" data-testid="validate-capabilities">
          <div class="bg-white rounded-lg p-4 border border-gray-200 text-center">
            <svg class="w-6 h-6 mx-auto mb-2 text-primary-600" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <p class="text-sm font-medium text-gray-700">Verificação segura</p>
          </div>
          <div class="bg-white rounded-lg p-4 border border-gray-200 text-center">
            <svg class="w-6 h-6 mx-auto mb-2 text-primary-600" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
            </svg>
            <p class="text-sm font-medium text-gray-700">Identificação do curso</p>
          </div>
          <div class="bg-white rounded-lg p-4 border border-gray-200 text-center">
            <svg class="w-6 h-6 mx-auto mb-2 text-primary-600" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
            </svg>
            <p class="text-sm font-medium text-gray-700">Confirmação do titular</p>
          </div>
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
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { validateCertificate } from '../api/certificates'
import { useTenantStore } from '../stores/tenant'
import AppAlert from '../components/AppAlert.vue'
import AppNavbar from '../components/AppNavbar.vue'

const tenantStore = useTenantStore()
const tenantName = computed(() => tenantStore.name || 'Plataforma de Cursos')
const route = useRoute()

const code = ref('')
const result = ref(null)
const loading = ref(false)
const serverError = ref('')

function formatDate(value) {
  if (!value) return '-'
  return new Date(value).toLocaleDateString('pt-BR')
}

async function handleSubmit() {
  loading.value = true
  result.value = null
  serverError.value = ''
  try {
    const { data } = await validateCertificate(code.value)
    result.value = data
  } catch (err) {
    if (err.response?.status === 404 || err.response?.status === 400) {
      result.value = { valid: false }
    } else {
      serverError.value = 'Não foi possível verificar o certificado. Tente novamente.'
    }
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  const queryCode = String(route.query.codigo || route.query.code || '').trim()
  if (queryCode) {
    code.value = queryCode
    handleSubmit()
  }
})
</script>
