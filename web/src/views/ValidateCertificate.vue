<template>
  <div class="min-h-screen bg-gray-50 flex flex-col">
    <header class="bg-primary-600 text-white py-6">
      <div class="max-w-3xl mx-auto px-4 text-center">
        <h1 class="text-2xl font-bold">Validar certificado</h1>
        <p class="text-white/80 text-sm mt-1">Confirme a autenticidade de um certificado emitido na plataforma.</p>
      </div>
    </header>

    <main class="flex-1 flex items-center justify-center p-6">
      <div class="w-full max-w-md bg-white rounded-lg shadow-lg p-8">
        <form class="space-y-4" @submit.prevent="handleSubmit">
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">Código de validação</label>
            <input
              v-model="code"
              type="text"
              required
              placeholder="Cole o código aqui"
              class="w-full p-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-600"
              data-testid="validate-code-input"
            />
          </div>
          <button
            type="submit"
            :disabled="loading"
            class="w-full py-3 bg-primary-600 text-white font-semibold rounded-lg hover:bg-primary-700 transition disabled:opacity-50"
            data-testid="validate-submit-btn"
          >
            {{ loading ? 'Verificando...' : 'Verificar' }}
          </button>
        </form>

        <!-- Loading state -->
        <div v-if="loading" class="mt-6 text-center">
          <svg class="animate-spin w-6 h-6 mx-auto text-primary-600" fill="none" viewBox="0 0 24 24">
            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
          </svg>
          <p class="text-sm text-gray-500 mt-2">Verificando...</p>
        </div>

        <!-- Server/network error -->
        <AppAlert v-else-if="serverError" type="error" data-testid="validate-server-error">
          {{ serverError }}
        </AppAlert>

        <!-- Valid certificate -->
        <div v-else-if="result && result.valid" class="mt-6 p-4 rounded-lg bg-green-50 text-green-800" data-testid="validate-valid">
          <div class="flex items-center gap-2 mb-3">
            <svg class="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
              <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd" />
            </svg>
            <p class="font-bold">Certificado válido</p>
          </div>
          <div class="space-y-1 text-sm">
            <p><span class="font-medium">Número:</span> {{ result.certificate_number }}</p>
            <p><span class="font-medium">Aluno:</span> {{ result.student_name }}</p>
            <p><span class="font-medium">Curso:</span> {{ result.course_name }}</p>
            <p><span class="font-medium">Emitido em:</span> {{ formatDate(result.issued_at) }}</p>
          </div>
        </div>

        <!-- Invalid/not found -->
        <div v-else-if="result && !result.valid" class="mt-6 p-4 rounded-lg bg-red-50 text-red-800" data-testid="validate-invalid">
          <div class="flex items-center gap-2 mb-1">
            <svg class="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
              <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clip-rule="evenodd" />
            </svg>
            <p class="font-bold">Código não encontrado</p>
          </div>
          <p class="text-sm">O certificado não foi localizado em nossa base de dados.</p>
        </div>
      </div>
    </main>

    <footer class="bg-gray-100 py-4 text-center text-sm text-gray-500">
      &copy; {{ new Date().getFullYear() }} {{ tenantName }}. Todos os direitos reservados.
    </footer>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { validateCertificate } from '../api/certificates'
import { useTenantStore } from '../stores/tenant'
import AppAlert from '../components/AppAlert.vue'

const tenantStore = useTenantStore()
const tenantName = computed(() => tenantStore.name || 'Plataforma de Cursos')

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
      // Not found / invalid code — show as "not found" result
      result.value = { valid: false }
    } else {
      // Network or server error — show as error
      serverError.value = 'Não foi possível verificar o certificado. Tente novamente.'
    }
  } finally {
    loading.value = false
  }
}
</script>
