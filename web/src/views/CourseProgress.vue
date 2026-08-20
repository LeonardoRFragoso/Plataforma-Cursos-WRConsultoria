<template>
  <div class="min-h-screen bg-gray-50">
    <AppNavbar />

    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div class="flex justify-between items-center mb-6">
        <div>
          <h1 class="text-2xl font-bold text-secondary-900">Progresso dos Alunos</h1>
          <p class="text-sm text-gray-600">{{ course.name }}</p>
        </div>
        <AppButton @click="goBack" class="bg-gray-600 text-white">
          Voltar para Aulas
        </AppButton>
      </div>

      <div v-if="loading" class="text-center py-8">
        <p class="text-gray-600">Carregando...</p>
      </div>

      <div v-else-if="progressData.length === 0" class="text-center py-8">
        <p class="text-gray-600">Nenhum aluno matriculado neste curso</p>
      </div>

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
                <span :class="statusClass(row.enrollment_status)">{{ row.enrollment_status }}</span>
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
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '../api/client'
import AppNavbar from '../components/AppNavbar.vue'
import AppButton from '../components/AppButton.vue'

const route = useRoute()
const router = useRouter()
const courseId = route.params.id

const course = ref({})
const progressData = ref([])
const loading = ref(true)

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
    console.error('Erro ao carregar curso:', error)
  }
}

const loadProgress = async () => {
  try {
    const response = await api.get(`/api/v1/lessons/courses/${courseId}/progress`)
    progressData.value = response.data
  } catch (error) {
    console.error('Erro ao carregar progresso:', error)
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
