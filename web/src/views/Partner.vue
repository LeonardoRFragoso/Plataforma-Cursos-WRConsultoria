<template>
  <div class="min-h-screen flex flex-col">
    <AppNavbar />

    <!-- Split layout: visual proposition (left) + form (right) -->
    <main class="flex-1 bg-gray-50">
      <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12 lg:py-16">
        <div class="grid grid-cols-1 lg:grid-cols-2 gap-10 lg:gap-16 items-stretch">
          <!-- ────────────────────────────────────────────────────────
               LEFT: Value proposition + institutional visual
               ──────────────────────────────────────────────────────── -->
          <div class="flex flex-col" data-testid="partner-proposition">
            <h1 class="text-3xl sm:text-4xl font-bold text-secondary-900 mb-4">
              Seja um parceiro
            </h1>
            <p class="text-lg text-gray-600 mb-8">
              Leve uma plataforma de treinamento personalizada para sua empresa.
            </p>

            <!-- Institutional visual — WR auth crop (photographic team, no embedded marketing text) -->
            <div
              v-if="authVisual"
              class="relative rounded-xl overflow-hidden shadow-lg mb-8 aspect-video"
              data-testid="partner-visual"
            >
              <img
                :src="authVisual.src"
                :alt="authVisual.alt"
                class="absolute inset-0 w-full h-full object-cover"
              />
              <div class="absolute inset-0 bg-gradient-to-t from-primary-900/50 to-transparent"></div>
            </div>

            <!-- Benefits -->
            <div class="space-y-4">
              <div class="flex items-start gap-3">
                <div class="flex-shrink-0 w-8 h-8 bg-primary-100 rounded-lg flex items-center justify-center">
                  <svg class="w-5 h-5 text-primary-600" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                </div>
                <div>
                  <h3 class="font-semibold text-secondary-900">Gestão completa</h3>
                  <p class="text-sm text-gray-600">Cursos, alunos, progresso e certificações em um só ambiente.</p>
                </div>
              </div>

              <div class="flex items-start gap-3">
                <div class="flex-shrink-0 w-8 h-8 bg-primary-100 rounded-lg flex items-center justify-center">
                  <svg class="w-5 h-5 text-primary-600" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M3.75 13.5l10.5-11.25L12 10.5h8.25L9.75 21.75 12 13.5H3.75z" />
                  </svg>
                </div>
                <div>
                  <h3 class="font-semibold text-secondary-900">Plataforma White Label</h3>
                  <p class="text-sm text-gray-600">Sua marca, suas cores e seu domínio em uma plataforma profissional.</p>
                </div>
              </div>

              <div class="flex items-start gap-3">
                <div class="flex-shrink-0 w-8 h-8 bg-primary-100 rounded-lg flex items-center justify-center">
                  <svg class="w-5 h-5 text-primary-600" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M9 17.25v1.007a3 3 0 01-.879 2.122L7.5 21h9l-.621-.621A3 3 0 0115 18.257V17.25m6-12V15a2.25 2.25 0 01-2.25 2.25H5.25A2.25 2.25 0 013 15V5.25m18 0A2.25 2.25 0 0018.75 3H5.25A2.25 2.25 0 003 5.25m18 0V12a2.25 2.25 0 01-2.25 2.25H5.25A2.25 2.25 0 013 12V5.25" />
                  </svg>
                </div>
                <div>
                  <h3 class="font-semibold text-secondary-900">Certificação verificável</h3>
                  <p class="text-sm text-gray-600">Certificados com código de validação online para seus alunos.</p>
                </div>
              </div>
            </div>
          </div>

          <!-- ────────────────────────────────────────────────────────
               RIGHT: Partner form
               ──────────────────────────────────────────────────────── -->
          <div class="bg-white rounded-xl shadow-lg border border-gray-200 p-8 lg:p-10" data-testid="partner-form-card">
            <!-- Success state -->
            <div v-if="submitted" class="text-center py-12 space-y-4" data-testid="partner-success">
              <div class="mx-auto w-16 h-16 bg-green-100 rounded-full flex items-center justify-center">
                <svg class="w-8 h-8 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7" />
                </svg>
              </div>
              <h2 class="text-xl font-semibold text-gray-900">Proposta recebida!</h2>
              <p class="text-gray-600">
                Sua proposta foi enviada com sucesso. Entraremos em contato em breve
                através do e-mail informado.
              </p>
              <button
                @click="resetForm"
                class="text-primary-600 hover:text-primary-700 font-medium text-sm"
                data-testid="partner-new-submission"
              >
                Enviar nova proposta
              </button>
            </div>

            <!-- Form -->
            <form v-else class="space-y-5" @submit.prevent="handleSubmit">
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">Empresa *</label>
                <input
                  v-model="form.company_name"
                  type="text"
                  required
                  class="w-full p-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
                  data-testid="partner-company-input"
                />
              </div>
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">CNPJ</label>
                <input
                  v-model="form.cnpj"
                  type="text"
                  class="w-full p-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
                  data-testid="partner-cnpj-input"
                />
              </div>
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">Nome do contato *</label>
                <input
                  v-model="form.contact_name"
                  type="text"
                  required
                  class="w-full p-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
                  data-testid="partner-contact-name-input"
                />
              </div>
              <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label class="block text-sm font-medium text-gray-700 mb-1">E-mail *</label>
                  <input
                    v-model="form.contact_email"
                    type="email"
                    required
                    class="w-full p-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
                    data-testid="partner-email-input"
                  />
                </div>
                <div>
                  <label class="block text-sm font-medium text-gray-700 mb-1">Telefone</label>
                  <input
                    v-model="form.contact_phone"
                    type="text"
                    class="w-full p-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
                    data-testid="partner-phone-input"
                  />
                </div>
              </div>
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">Mensagem</label>
                <textarea
                  v-model="form.message"
                  rows="3"
                  class="w-full p-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
                  data-testid="partner-message-input"
                />
              </div>

              <AppAlert v-if="error" type="error" data-testid="partner-error">{{ error }}</AppAlert>

              <button
                type="submit"
                :disabled="loading"
                class="w-full py-3 bg-primary-600 text-white font-semibold rounded-lg hover:bg-primary-700 transition disabled:opacity-50"
                data-testid="partner-submit-btn"
              >
                {{ loading ? 'Enviando...' : 'Enviar proposta' }}
              </button>
            </form>
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
import { reactive, ref, computed } from 'vue'
import { submitPartnerLead } from '../api/partner'
import { useTenantStore } from '../stores/tenant'
import { getWrAuthVisual } from '../utils/courseMedia'
import AppAlert from '../components/AppAlert.vue'
import AppNavbar from '../components/AppNavbar.vue'

const tenantStore = useTenantStore()
const tenantName = computed(() => tenantStore.name || 'Plataforma de Cursos')
const authVisual = computed(() => getWrAuthVisual())

const form = reactive({
  company_name: '',
  cnpj: '',
  contact_name: '',
  contact_email: '',
  contact_phone: '',
  message: '',
})

const loading = ref(false)
const error = ref('')
const submitted = ref(false)

async function handleSubmit() {
  if (loading.value) return
  loading.value = true
  error.value = ''
  try {
    await submitPartnerLead(form)
    submitted.value = true
  } catch (err) {
    error.value = err.response?.data?.detail || 'Erro ao enviar proposta. Tente novamente.'
  } finally {
    loading.value = false
  }
}

function resetForm() {
  Object.keys(form).forEach((k) => (form[k] = ''))
  submitted.value = false
  error.value = ''
}
</script>
