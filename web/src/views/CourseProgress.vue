<template>
  <div>
    <AppPageHeader title="Progresso dos Alunos" :description="course.name">
      <template #actions>
        <AppButton @click="goBack" class="bg-gray-600 text-white" data-testid="back-to-lessons-btn">
          Voltar para Aulas
        </AppButton>
      </template>
    </AppPageHeader>

      <!-- Loading -->
      <LoadingState v-if="loading" message="Carregando progresso..." />

      <!-- Error -->
      <AppAlert v-else-if="loadError" type="error" closable @close="loadError = ''">
        {{ loadError }}
        <button @click="loadProgress" class="underline ml-2">Tentar novamente</button>
      </AppAlert>

      <!-- Empty -->
      <EmptyState
        v-else-if="progressData.length === 0"
        title="Nenhum aluno matriculado"
        description="Os alunos matricululados neste curso aparecerão aqui com seu progresso."
      />

      <!-- Success -->
      <div v-else class="overflow-x-auto">
        <table class="min-w-full bg-white rounded-lg shadow">
          <thead class="bg-gray-100">
            <tr>
              <th class="px-4 py-3 text-left text-xs font-medium text-gray-600 uppercase">Aluno</th>
              <th class="px-4 py-3 text-left text-xs font-medium text-gray-600 uppercase">Turma</th>
              <th class="px-4 py-3 text-left text-xs font-medium text-gray-600 uppercase">Status</th>
              <th class="px-4 py-3 text-center text-xs font-medium text-gray-600 uppercase">Aulas Obrigatórias</th>
              <th class="px-4 py-3 text-center text-xs font-medium text-gray-600 uppercase">Progresso</th>
              <th class="px-4 py-3 text-center text-xs font-medium text-gray-600 uppercase">Certificado</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-gray-200">
            <tr v-for="row in progressData" :key="row.student_id">
              <td class="px-4 py-3 text-sm text-gray-900">{{ row.student_name }}</td>
              <td class="px-4 py-3 text-sm text-gray-600">{{ row.class_name }}</td>
              <td class="px-4 py-3 text-sm">
                <span :class="statusClass(row.enrollment_status)">{{ formatStatus(row.enrollment_status) }}</span>
              </td>
              <td class="px-4 py-3 text-sm text-center text-gray-600">
                {{ row.required_completed }} / {{ row.required_total }}
              </td>
              <td class="px-4 py-3 text-sm text-center">
                <div class="flex items-center gap-2">
                  <div class="w-24 bg-gray-200 rounded-full h-2">
                    <div
                      class="bg-primary-600 h-2 rounded-full"
                      :style="{ width: `${row.percentage}%` }"
                    ></div>
                  </div>
                  <span class="text-xs text-gray-600">{{ row.percentage }}%</span>
                </div>
              </td>
              <td class="px-4 py-3 text-sm text-center">
                <span v-if="row.certificate_status === 'Sim'" class="text-green-600 font-medium">Sim</span>
                <span v-else class="text-gray-400">Não</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '../api/client'
import AppPageHeader from '../components/AppPageHeader.vue'
import AppButton from '../components/AppButton.vue'
import AppAlert from '../components/AppAlert.vue'
import EmptyState from '../components/EmptyState.vue'
import LoadingState from '../components/LoadingState.vue'

const route = useRoute()
const router = useRouter()
const courseId = route.params.id

const course = ref({})
const progressData = ref([])
const loading = ref(true)
const loadError = ref('')

const formatStatus = (status) => {
  const map = {
    'CONFIRMADA': 'Confirmada',
    'CONCLUIDA': 'Concluída',
    'PENDENTE': 'Pendente',
    'CANCELADA': 'Cancelada',
  }
  return map[status] || status
}

const statusClass = (status) => {
  const classes = {
    'CONFIRMADA': 'text-green-600',
    'CONCLUIDA': 'text-blue-600',
    'PENDENTE': 'text-yellow-600',
    'CANCELADA': 'text-red-600',
  }
  return classes[status] || 'text-gray-600'
}

const loadCourse = async () => {
  try {
    const response = await api.get(`/api/v1/courses/${courseId}`)
    course.value = response.data
  } catch (error) {
    // silent — course name is display-only
  }
}

const loadProgress = async () => {
  loading.value = true
  loadError.value = ''
  try {
    const response = await api.get(`/api/v1/lessons/courses/${courseId}/progress`)
    progressData.value = response.data
  } catch (error) {
    loadError.value = 'Não foi possível carregar o progresso. Tente novamente.'
  } finally {
    loading.value = false
  }
}

const goBack = () => {
  router.push(`/courses/${courseId}/lessons`)
}

onMounted(() => {
  loadCourse()
  loadProgress()
})
</script>
