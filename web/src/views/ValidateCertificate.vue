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
              <label class="block text-sm font-medium text-gray-700 mb-1.5" for="validate-code-input">Código de validação</label>
              <input
                id="validate-code-input"
                v-model="code"
                type="text"
                required
                placeholder="Cole o código de validação aqui"
                class="w-full p-3.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 text-base"
                data-testid="validate-code-input"
                autocomplete="off"
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

          <!-- Result -->
          <div v-else-if="result" class="mt-8">
            <!-- Demo banner (shown before any status card so it can never be
                 confused with an official certificate) -->
            <div
              v-if="result.is_demo"
              class="mb-4 p-4 rounded-xl bg-amber-50 border-2 border-amber-300"
              data-testid="validate-demo-banner"
              role="status"
            >
              <div class="flex items-start gap-3">
                <svg class="w-6 h-6 text-amber-600 flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z" />
                </svg>
                <div>
                  <p class="font-bold text-amber-800">Certificado de demonstração</p>
                  <p class="text-sm text-amber-700 mt-1">
                    Este registro foi criado exclusivamente para apresentação e testes da
                    plataforma. Não possui validade oficial.
                  </p>
                </div>
              </div>
            </div>

            <!-- ACTIVE -->
            <div
              v-if="result.valid"
              class="p-6 rounded-xl bg-green-50 border-2 border-green-200"
              data-testid="validate-valid"
            >
              <div class="flex items-center gap-3 mb-5">
                <div class="flex-shrink-0 w-12 h-12 bg-green-500 rounded-full flex items-center justify-center">
                  <svg class="w-7 h-7 text-white" fill="currentColor" viewBox="0 0 20 20">
                    <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd" />
                  </svg>
                </div>
                <div>
                  <p class="text-lg font-bold text-green-800">
                    {{ result.is_demo ? 'Registro de demonstração válido' : 'Certificado válido' }}
                  </p>
                  <p class="text-sm text-green-600">Autenticidade confirmada</p>
                </div>
              </div>
              <CertificateDetails :result="result" :format-date="formatDate" />
            </div>

            <!-- EXPIRED -->
            <div
              v-else-if="result.status === 'EXPIRED'"
              class="p-6 rounded-xl bg-yellow-50 border-2 border-yellow-200"
              data-testid="validate-expired"
            >
              <div class="flex items-center gap-3 mb-2">
                <div class="flex-shrink-0 w-12 h-12 bg-yellow-500 rounded-full flex items-center justify-center">
                  <svg class="w-7 h-7 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M12 6v6h4.5m4.5 0a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                </div>
                <div>
                  <p class="text-lg font-bold text-yellow-800">Certificado expirado</p>
                  <p class="text-sm text-yellow-700">A validade do certificado foi ultrapassada</p>
                </div>
              </div>
              <CertificateDetails :result="result" :format-date="formatDate" />
            </div>

            <!-- REVOKED -->
            <div
              v-else-if="result.status === 'REVOKED'"
              class="p-6 rounded-xl bg-red-50 border-2 border-red-200"
              data-testid="validate-revoked"
            >
              <div class="flex items-center gap-3 mb-2">
                <div class="flex-shrink-0 w-12 h-12 bg-red-500 rounded-full flex items-center justify-center">
                  <svg class="w-7 h-7 text-white" fill="currentColor" viewBox="0 0 20 20">
                    <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clip-rule="evenodd" />
                  </svg>
                </div>
                <div>
                  <p class="text-lg font-bold text-red-800">Certificado revogado</p>
                  <p class="text-sm text-red-600">Este certificado foi revogado pela instituição</p>
                </div>
              </div>
              <p v-if="result.revocation_reason" class="text-sm text-red-700 mt-2">
                Motivo: {{ result.revocation_reason }}
              </p>
              <CertificateDetails :result="result" :format-date="formatDate" />
            </div>

            <!-- SUPERSEDED -->
            <div
              v-else-if="result.status === 'SUPERSEDED'"
              class="p-6 rounded-xl bg-blue-50 border-2 border-blue-200"
              data-testid="validate-superseded"
            >
              <div class="flex items-center gap-3 mb-2">
                <div class="flex-shrink-0 w-12 h-12 bg-blue-500 rounded-full flex items-center justify-center">
                  <svg class="w-7 h-7 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0l3.181 3.183a8.25 8.25 0 0011.667 0l3.181-3.183m-4.991-2.696v4.992m0 0h-4.992" />
                  </svg>
                </div>
                <div>
                  <p class="text-lg font-bold text-blue-800">Certificado substituído</p>
                  <p class="text-sm text-blue-600">Substituído por uma nova versão</p>
                </div>
              </div>
              <CertificateDetails :result="result" :format-date="formatDate" />
            </div>

            <!-- NOT_FOUND -->
            <div
              v-else
              class="p-6 rounded-xl bg-red-50 border-2 border-red-200"
              data-testid="validate-invalid"
            >
              <div class="flex items-center gap-3 mb-2">
                <div class="flex-shrink-0 w-12 h-12 bg-red-500 rounded-full flex items-center justify-center">
                  <svg class="w-7 h-7 text-white" fill="currentColor" viewBox="0 0 20 20">
                    <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clip-rule="evenodd" />
                  </svg>
                </div>
                <div>
                  <p class="text-lg font-bold text-red-800">Certificado não encontrado</p>
                  <p class="text-sm text-red-600">Verificação sem resultado</p>
                </div>
              </div>
              <p class="text-sm text-red-700 mt-3">O certificado não foi localizado em nossa base de dados. Confira o código e tente novamente.</p>
            </div>
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
import CertificateDetails from '../components/CertificateDetails.vue'

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

async function runValidation(value) {
  loading.value = true
  result.value = null
  serverError.value = ''
  try {
    const { data } = await validateCertificate(value)
    result.value = data
  } catch (err) {
    if (err.response?.status === 404 || err.response?.status === 400) {
      result.value = { valid: false, status: 'NOT_FOUND' }
    } else {
      serverError.value = 'Não foi possível verificar o certificado. Tente novamente.'
    }
  } finally {
    loading.value = false
  }
}

async function handleSubmit() {
  await runValidation(code.value)
}

// Auto-validation from query param (?codigo= or ?code= for backwards compat).
onMounted(async () => {
  const queryCode = route.query.codigo || route.query.code
  if (queryCode && typeof queryCode === 'string' && queryCode.trim()) {
    code.value = queryCode.trim()
    await runValidation(code.value)
  }
})
</script>
