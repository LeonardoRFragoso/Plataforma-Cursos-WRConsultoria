<template>
  <div class="flex items-center justify-center min-h-[60vh] px-4">
    <div class="max-w-md w-full bg-white rounded-lg shadow-lg border border-gray-200 p-8">
      <!-- Loading state -->
      <div v-if="loading" class="text-center py-8">
        <div class="inline-block animate-spin rounded-full h-10 w-10 border-4 border-primary-200 border-t-primary-600 mb-4"></div>
        <p class="text-gray-600 font-medium">Carregando pagamento...</p>
      </div>

      <!-- Error state -->
      <div v-else-if="error" class="text-center py-8">
        <div class="text-red-500 text-4xl mb-3">⚠</div>
        <p class="text-red-600 font-medium mb-2">{{ error }}</p>
        <button
          @click="loadPayment"
          data-testid="retry-btn"
          class="mt-4 bg-gray-100 text-gray-700 px-6 py-2 rounded-md text-sm font-medium hover:bg-gray-200"
        >
          Tentar novamente
        </button>
      </div>

      <!-- Processing state — payment created but not yet confirmed -->
      <div v-else-if="isProcessing" class="text-center py-6">
        <div class="inline-block animate-spin rounded-full h-10 w-10 border-4 border-yellow-200 border-t-yellow-600 mb-4"></div>
        <h2 class="text-lg font-bold text-gray-900 mb-2">Estamos confirmando seu pagamento...</h2>
        <p class="text-sm text-gray-500 mb-4">
          Isso pode levar alguns instantes. Assim que a operadora confirmar, o acesso ao curso será liberado.
        </p>
        <p class="text-xs text-gray-400 mb-4">
          Status atual: <span class="font-medium">{{ payment.status }}</span>
        </p>
        <button
          @click="loadPayment"
          data-testid="refresh-btn"
          :disabled="polling"
          class="bg-gray-100 text-gray-700 px-6 py-2 rounded-md text-sm font-medium hover:bg-gray-200 disabled:opacity-50"
        >
          {{ polling ? 'Verificando...' : 'Verificar agora' }}
        </button>
      </div>

      <!-- Approved state -->
      <div v-else-if="payment.status === 'APROVADO'" class="text-center py-6">
        <div class="text-green-500 text-5xl mb-3">✓</div>
        <h2 class="text-lg font-bold text-green-700 mb-2">Pagamento confirmado!</h2>
        <p class="text-sm text-gray-600 mb-4">Sua matrícula foi confirmada com sucesso.</p>
        <div class="space-y-2">
          <router-link
            v-if="payment.course_id"
            :to="`/courses/${payment.course_id}/learn`"
            data-testid="access-course-link"
            class="block bg-primary-600 text-white px-6 py-3 rounded-md text-sm font-medium hover:bg-primary-700"
          >
            Acessar Curso
          </router-link>
          <router-link
            to="/dashboard"
            data-testid="back-dashboard-link"
            class="block bg-gray-100 text-gray-700 px-6 py-2 rounded-md text-sm font-medium hover:bg-gray-200"
          >
            Voltar ao Dashboard
          </router-link>
        </div>
      </div>

      <!-- Refused state -->
      <div v-else-if="payment.status === 'RECUSADO'" class="text-center py-6">
        <div class="text-red-500 text-5xl mb-3">✗</div>
        <h2 class="text-lg font-bold text-red-700 mb-2">Pagamento recusado</h2>
        <p class="text-sm text-gray-600 mb-4">
          Esta tentativa foi encerrada. Para tentar novamente, inicie um novo pagamento pelo curso.
        </p>
        <router-link
          v-if="payment.course_id"
          :to="`/courses/${payment.course_id}`"
          data-testid="retry-payment-link"
          class="block bg-primary-600 text-white px-6 py-3 rounded-md text-sm font-medium hover:bg-primary-700"
        >
          Voltar ao curso e tentar novamente
        </router-link>
        <router-link
          v-else
          to="/cursos"
          data-testid="retry-payment-link"
          class="block bg-primary-600 text-white px-6 py-3 rounded-md text-sm font-medium hover:bg-primary-700"
        >
          Voltar ao catálogo
        </router-link>
        <router-link
          to="/dashboard"
          class="block mt-2 bg-gray-100 text-gray-700 px-6 py-2 rounded-md text-sm font-medium hover:bg-gray-200"
        >
          Voltar ao Dashboard
        </router-link>
      </div>

      <!-- Expired state -->
      <div v-else-if="payment.status === 'EXPIRADO'" class="text-center py-6">
        <div class="text-yellow-500 text-5xl mb-3">⌛</div>
        <h2 class="text-lg font-bold text-gray-900 mb-2">Pagamento expirado</h2>
        <p class="text-sm text-gray-600 mb-4">
          Esta tentativa não pode mais ser utilizada. Você pode iniciar um novo pagamento pelo curso sem reutilizar a cobrança anterior.
        </p>
        <router-link
          v-if="payment.course_id"
          :to="`/courses/${payment.course_id}`"
          data-testid="expired-payment-link"
          class="block bg-primary-600 text-white px-6 py-3 rounded-md text-sm font-medium hover:bg-primary-700"
        >
          Voltar ao curso e gerar novo pagamento
        </router-link>
        <router-link
          v-else
          to="/cursos"
          data-testid="expired-payment-link"
          class="block bg-primary-600 text-white px-6 py-3 rounded-md text-sm font-medium hover:bg-primary-700"
        >
          Voltar ao catálogo
        </router-link>
        <router-link
          to="/dashboard"
          class="block mt-2 bg-gray-100 text-gray-700 px-6 py-2 rounded-md text-sm font-medium hover:bg-gray-200"
        >
          Voltar ao Dashboard
        </router-link>
      </div>

      <!-- Refunded state -->
      <div v-else-if="payment.status === 'REEMBOLSADO'" class="text-center py-6">
        <div class="text-blue-500 text-5xl mb-3">↩</div>
        <h2 class="text-lg font-bold text-blue-700 mb-2">Pagamento reembolsado</h2>
        <p class="text-sm text-gray-600 mb-4">O valor foi estornado.</p>
        <router-link
          to="/dashboard"
          class="block bg-gray-100 text-gray-700 px-6 py-2 rounded-md text-sm font-medium hover:bg-gray-200"
        >
          Voltar ao Dashboard
        </router-link>
      </div>

      <!-- Timeout state — polling stopped without confirmation -->
      <div v-else-if="timedOut" class="text-center py-6">
        <div class="text-yellow-500 text-5xl mb-3">⏱</div>
        <h2 class="text-lg font-bold text-gray-900 mb-2">Aguardando confirmação</h2>
        <p class="text-sm text-gray-600 mb-4">
          O pagamento ainda está sendo processado pela operadora. Você pode verificar novamente agora ou consultar o status mais tarde.
        </p>
        <p class="text-xs text-gray-400 mb-4">
          Status atual: <span class="font-medium">{{ payment.status }}</span>
        </p>
        <div class="space-y-2">
          <button
            @click="startPolling"
            data-testid="resume-polling-btn"
            class="block w-full bg-primary-600 text-white px-6 py-2 rounded-md text-sm font-medium hover:bg-primary-700"
          >
            Verificar novamente
          </button>
          <router-link
            to="/dashboard"
            class="block bg-gray-100 text-gray-700 px-6 py-2 rounded-md text-sm font-medium hover:bg-gray-200"
          >
            Voltar ao Dashboard
          </router-link>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { useRoute } from 'vue-router'
import api from '../api/client'

const route = useRoute()
const paymentId = route.params.paymentId

const payment = ref({})
const loading = ref(true)
const polling = ref(false)
const error = ref('')
const timedOut = ref(false)

// Polling configuration — bounded period
const MAX_POLL_DURATION_MS = 120000 // 2 minutes max
const POLL_INTERVAL_MS = 5000 // 5 seconds between polls
let pollTimer = null
let pollStartTime = null

const isProcessing = computed(() => {
  const s = payment.value.status
  return s === 'PENDENTE' || s === 'PROCESSANDO'
})

onMounted(async () => {
  await loadPayment()
})

onUnmounted(() => {
  stopPolling()
})

async function loadPayment() {
  loading.value = true
  error.value = ''
  timedOut.value = false
  try {
    const { data } = await api.get(`/api/v1/payments/${paymentId}`)
    payment.value = data
    // If payment is still processing, start polling the internal API
    if (isProcessing.value) {
      startPolling()
    }
  } catch (e) {
    error.value = e.response?.data?.detail || 'Erro ao carregar pagamento'
  } finally {
    loading.value = false
  }
}

function startPolling() {
  stopPolling()
  timedOut.value = false
  pollStartTime = Date.now()
  polling.value = true
  pollTimer = setInterval(async () => {
    // Check timeout
    if (Date.now() - pollStartTime > MAX_POLL_DURATION_MS) {
      stopPolling()
      timedOut.value = true
      return
    }
    try {
      const { data } = await api.get(`/api/v1/payments/${paymentId}`)
      payment.value = data
      // Stop polling when we reach a terminal state
      if (!isProcessing.value) {
        stopPolling()
      }
    } catch {
      // Silently ignore poll errors — keep trying until timeout
    }
  }, POLL_INTERVAL_MS)
}

function stopPolling() {
  polling.value = false
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}
</script>