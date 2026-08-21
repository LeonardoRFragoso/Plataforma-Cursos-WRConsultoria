<template>
  <AuthLayout>
    <div class="bg-white rounded-xl shadow-lg border border-gray-200 p-8 sm:p-10" data-testid="forgot-card">
      <div class="mb-8">
        <h1 class="text-2xl font-bold text-secondary-900 mb-2">Recuperar senha</h1>
        <p class="text-sm text-gray-500">Informe seu e-mail para receber as instruções.</p>
      </div>

      <!-- Initial form -->
      <form v-if="!submitted" class="space-y-5" @submit.prevent="handleSubmit">
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1.5">E-mail</label>
          <input
            v-model="email"
            type="email"
            required
            placeholder="seu@email.com"
            class="w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-colors"
            data-testid="forgot-email-input"
          />
        </div>

        <div v-if="error" class="p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm" data-testid="forgot-error">
          {{ error }}
        </div>

        <button
          type="submit"
          :disabled="loading"
          class="w-full py-3 bg-primary-600 text-white font-semibold rounded-lg hover:bg-primary-700 transition-colors disabled:opacity-60 disabled:cursor-not-allowed"
          data-testid="forgot-submit-btn"
        >
          {{ loading ? 'Enviando...' : 'Enviar instruções' }}
        </button>

        <div class="text-center pt-2">
          <router-link
            to="/login"
            class="text-sm text-primary-600 hover:text-primary-700 font-medium"
            data-testid="back-to-login-link"
          >
            Voltar para o login
          </router-link>
        </div>
      </form>

      <!-- Success state -->
      <div v-else class="text-center space-y-4" data-testid="forgot-success">
        <div class="mx-auto w-14 h-14 bg-green-100 rounded-full flex items-center justify-center">
          <svg class="w-7 h-7 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7" />
          </svg>
        </div>
        <h2 class="text-lg font-semibold text-secondary-900">Solicitação recebida</h2>
        <p class="text-sm text-gray-600">
          Se o e-mail informado estiver cadastrado, você receberá as instruções
          de recuperação de senha.
        </p>
        <p v-if="devToken" class="text-xs text-gray-400 bg-gray-50 p-3 rounded-md break-all" data-testid="dev-reset-token">
          <strong>AMBIENTE DE DESENVOLVIMENTO:</strong> seu token de redefinição é<br>
          <code>{{ devToken }}</code>
        </p>
        <p v-if="devToken" class="text-xs text-gray-500">
          Use este token na tela de redefinição de senha. Em produção, o token seria enviado por e-mail.
        </p>
        <router-link
          to="/login"
          class="inline-block text-sm text-primary-600 hover:text-primary-700 font-medium"
        >
          Voltar para o login
        </router-link>
      </div>
    </div>
  </AuthLayout>
</template>

<script setup>
import { ref } from 'vue'
import AuthLayout from '../layouts/AuthLayout.vue'
import api from '../api/client'

const email = ref('')
const loading = ref(false)
const error = ref('')
const submitted = ref(false)
const devToken = ref('')

// Fail-closed: only expose raw reset token in DEV with explicit opt-in flag.
// Production, staging, and preview builds must NEVER display reset tokens
// even if the backend accidentally returns the field.
const canExposeDevToken =
  import.meta.env.DEV &&
  import.meta.env.VITE_ALLOW_DEV_RESET_TOKEN === 'true'

async function handleSubmit() {
  loading.value = true
  error.value = ''
  try {
    const response = await api.post('/api/v1/auth/forgot-password', {
      email: email.value,
    })
    // Only store dev token if explicitly allowed (fail-closed by default)
    if (canExposeDevToken && response.data?.reset_token) {
      devToken.value = response.data.reset_token
    }
    submitted.value = true
  } catch (err) {
    // Generic response — don't reveal whether email exists
    submitted.value = true
  } finally {
    loading.value = false
  }
}
</script>
