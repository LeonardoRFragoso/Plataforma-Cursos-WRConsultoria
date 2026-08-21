<template>
  <div class="min-h-screen bg-gradient-to-br from-slate-900 to-slate-800 p-6">
    <div class="max-w-xl mx-auto bg-white rounded-2xl shadow-xl p-8 mt-10">
      <h1 class="text-2xl font-bold text-gray-800 mb-2">Seja um parceiro</h1>
      <p class="text-gray-600 mb-6">
        Preencha seus dados e entraremos em contato para ativar sua plataforma
        white label.
      </p>

      <!-- Success state -->
      <div v-if="submitted" class="text-center py-8 space-y-4" data-testid="partner-success">
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
      <form v-else class="space-y-4" @submit.prevent="handleSubmit">
        <div>
          <label class="block text-sm font-medium text-gray-700">Empresa *</label>
          <input
            v-model="form.company_name"
            type="text"
            required
            class="w-full p-3 border rounded-lg focus:outline-none focus:ring-2 focus:ring-primary"
            data-testid="partner-company-input"
          />
        </div>
        <div>
          <label class="block text-sm font-medium text-gray-700">CNPJ</label>
          <input
            v-model="form.cnpj"
            type="text"
            class="w-full p-3 border rounded-lg focus:outline-none focus:ring-2 focus:ring-primary"
            data-testid="partner-cnpj-input"
          />
        </div>
        <div>
          <label class="block text-sm font-medium text-gray-700">Nome do contato *</label>
          <input
            v-model="form.contact_name"
            type="text"
            required
            class="w-full p-3 border rounded-lg focus:outline-none focus:ring-2 focus:ring-primary"
            data-testid="partner-contact-name-input"
          />
        </div>
        <div>
          <label class="block text-sm font-medium text-gray-700">E-mail *</label>
          <input
            v-model="form.contact_email"
            type="email"
            required
            class="w-full p-3 border rounded-lg focus:outline-none focus:ring-2 focus:ring-primary"
            data-testid="partner-email-input"
          />
        </div>
        <div>
          <label class="block text-sm font-medium text-gray-700">Telefone</label>
          <input
            v-model="form.contact_phone"
            type="text"
            class="w-full p-3 border rounded-lg focus:outline-none focus:ring-2 focus:ring-primary"
            data-testid="partner-phone-input"
          />
        </div>
        <div>
          <label class="block text-sm font-medium text-gray-700">Mensagem</label>
          <textarea
            v-model="form.message"
            rows="3"
            class="w-full p-3 border rounded-lg focus:outline-none focus:ring-2 focus:ring-primary"
            data-testid="partner-message-input"
          />
        </div>

        <AppAlert v-if="error" type="error" data-testid="partner-error">{{ error }}</AppAlert>

        <button
          type="submit"
          :disabled="loading"
          class="w-full py-3 bg-primary text-white font-semibold rounded-lg hover:opacity-90 transition disabled:opacity-50"
          data-testid="partner-submit-btn"
        >
          {{ loading ? 'Enviando...' : 'Enviar proposta' }}
        </button>
      </form>
    </div>
  </div>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { submitPartnerLead } from '../api/partner'
import AppAlert from '../components/AppAlert.vue'

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
  if (loading.value) return // prevent duplicate submission
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
