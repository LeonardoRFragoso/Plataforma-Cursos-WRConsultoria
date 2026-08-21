<template>
  <div>
    <div class="flex items-center justify-center min-h-[60vh]">
    <div class="max-w-md w-full bg-white rounded-lg shadow-lg border border-gray-200 p-8">
      <div v-if="loading" class="text-center text-gray-500">Carregando...</div>
      <div v-else-if="error" class="text-center text-red-600">{{ error }}</div>
      <div v-else>
        <h1 class="text-xl font-bold text-secondary-900 mb-1">Simulador de Pagamento</h1>
        <p class="text-xs text-gray-400 mb-6">DEMO MODE — não é uma transação real</p>

        <div class="space-y-3 mb-6">
          <div class="flex justify-between text-sm">
            <span class="text-gray-500">Curso</span>
            <span class="font-medium text-gray-900">{{ payment.course_name }}</span>
          </div>
          <div class="flex justify-between text-sm">
            <span class="text-gray-500">Aluno</span>
            <span class="font-medium text-gray-900">{{ payment.student_name }}</span>
          </div>
          <div class="flex justify-between text-sm">
            <span class="text-gray-500">Valor</span>
            <span class="font-medium text-gray-900">R$ {{ payment.amount?.toFixed(2) }}</span>
          </div>
          <div class="flex justify-between text-sm">
            <span class="text-gray-500">Status</span>
            <span :class="statusClass">{{ payment.status }}</span>
          </div>
        </div>

        <div v-if="payment.status === 'APROVADO'" class="text-center mb-4">
          <p class="text-green-600 font-medium">Pagamento aprovado! Matrícula confirmada.</p>
          <router-link
            v-if="payment.enrollment_status === 'CONFIRMADA' && payment.course_id"
            :to="`/courses/${payment.course_id}/learn`"
            data-testid="access-course-link"
            class="mt-3 inline-block bg-primary-600 text-white px-6 py-2 rounded-md text-sm font-medium hover:bg-primary-700"
          >
            Acessar Curso
          </router-link>
        </div>

        <div v-else class="space-y-3">
          <button
            @click="simulate('approve')"
            :disabled="acting"
            data-testid="approve-btn"
            class="w-full bg-green-600 text-white py-3 rounded-md font-medium hover:bg-green-700 disabled:opacity-50"
          >
            Simular Pagamento Aprovado
          </button>
          <button
            @click="simulate('pending')"
            :disabled="acting"
            data-testid="pending-btn"
            class="w-full bg-yellow-500 text-white py-2 rounded-md text-sm font-medium hover:bg-yellow-600 disabled:opacity-50"
          >
            Simular Pendente
          </button>
          <button
            @click="simulate('reject')"
            :disabled="acting"
            data-testid="reject-btn"
            class="w-full bg-red-500 text-white py-2 rounded-md text-sm font-medium hover:bg-red-600 disabled:opacity-50"
          >
            Simular Rejeitado
          </button>
        </div>
      </div>
    </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import api from '../api/client'

const route = useRoute()
const paymentId = route.params.paymentId

const payment = ref({})
const loading = ref(true)
const acting = ref(false)
const error = ref('')

onMounted(async () => {
  try {
    const { data } = await api.get(`/api/v1/payments/demo/${paymentId}`)
    payment.value = data
  } catch (e) {
    error.value = e.response?.data?.detail || 'Erro ao carregar pagamento'
  } finally {
    loading.value = false
  }
})

async function simulate(action) {
  acting.value = true
  error.value = ''
  try {
    const { data } = await api.post(`/api/v1/payments/demo/${paymentId}/${action}`)
    payment.value = { ...payment.value, ...data }
    // Reload full status
    const { data: fresh } = await api.get(`/api/v1/payments/demo/${paymentId}`)
    payment.value = fresh
  } catch (e) {
    error.value = e.response?.data?.detail || 'Erro na simulação'
  } finally {
    acting.value = false
  }
}

function statusClass(status) {
  const map = {
    APROVADO: 'text-green-600 font-medium',
    PENDENTE: 'text-yellow-600 font-medium',
    PROCESSANDO: 'text-yellow-600 font-medium',
    RECUSADO: 'text-red-600 font-medium',
  }
  return map[status] || 'text-gray-500'
}
</script>
