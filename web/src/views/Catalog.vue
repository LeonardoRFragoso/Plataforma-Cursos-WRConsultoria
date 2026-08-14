<template>
  <div class="min-h-screen bg-gray-50">
    <AppNavbar />

    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div class="text-center mb-10">
        <h1 class="text-3xl font-bold text-secondary-900 mb-2">Cursos disponíveis</h1>
        <p class="text-gray-600">Escolha um curso e comece sua jornada</p>
      </div>

      <div v-if="loading" class="text-center py-12">
        <p class="text-gray-600" role="status" aria-live="polite">Carregando cursos...</p>
      </div>

      <div v-else-if="error" class="text-center py-12" role="alert" aria-live="polite">
        <p class="text-red-600 mb-4">{{ error }}</p>
        <AppButton @click="loadCourses" class="bg-primary-600 text-white">Tentar novamente</AppButton>
      </div>

      <div v-else-if="courses.length === 0" class="text-center py-12" role="status" aria-live="polite">
        <p class="text-gray-600">Nenhum curso disponível no momento.</p>
      </div>

      <div v-else class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        <AppCard v-for="course in courses" :key="course.id" class="hover:shadow-lg transition-shadow flex flex-col">
          <template #header>
            <h2 class="text-lg font-semibold text-secondary-900">{{ course.name }}</h2>
          </template>
          <div class="space-y-2 text-sm flex-1">
            <p v-if="course.code"><strong>Código:</strong> {{ course.code }}</p>
            <p v-if="course.category"><strong>Categoria:</strong> {{ course.category }}</p>
            <p v-if="course.modality"><strong>Modalidade:</strong> {{ formatModality(course.modality) }}</p>
            <p v-if="course.carga_horaria"><strong>Carga horária:</strong> {{ course.carga_horaria }}h</p>
            <p v-if="course.price !== undefined"><strong>Preço:</strong> R$ {{ formatPrice(course.price) }}</p>
            <p v-if="course.description" class="text-gray-600 mt-2 line-clamp-3">{{ course.description }}</p>
          </div>

          <div class="mt-4 pt-4 border-t border-gray-100">
            <AppButton
              v-if="!isAuthenticated"
              @click="goTo('/login')"
              class="w-full bg-primary-600 text-white"
              aria-label="Entrar para continuar"
            >
              Entrar para continuar
            </AppButton>

            <AppButton
              v-else-if="isEnrolled(course.id)"
              @click="goTo(`/courses/${course.id}/learn`)"
              class="w-full bg-primary-600 text-white"
              aria-label="Acessar curso"
            >
              Acessar curso
            </AppButton>

            <AppButton
              v-else-if="isStudent"
              @click="goTo(`/courses/${course.id}`)"
              class="w-full bg-primary-600 text-white"
              aria-label="Ver detalhes"
            >
              Ver detalhes
            </AppButton>

            <AppButton
              v-else
              @click="goTo(`/courses/${course.id}`)"
              class="w-full bg-primary-600 text-white"
              aria-label="Ver detalhes"
            >
              Ver detalhes
            </AppButton>
          </div>
        </AppCard>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import api from '../api/client'
import AppNavbar from '../components/AppNavbar.vue'
import AppCard from '../components/AppCard.vue'
import AppButton from '../components/AppButton.vue'

const authStore = useAuthStore()
const router = useRouter()

const courses = ref([])
const enrollments = ref([])
const loading = ref(true)
const error = ref(null)

const isAuthenticated = computed(() => authStore.isAuthenticated)
const isStudent = computed(() => authStore.userRole?.toLowerCase() === 'student')

const formatModality = (modality) => {
  const map = {
    PRESENCIAL: 'Presencial',
    EAD: 'EAD',
    SEMIPRESENCIAL: 'Semipresencial',
  }
  return map[modality] || modality
}

const formatPrice = (price) => {
  return parseFloat(price || 0).toFixed(2).replace('.', ',')
}

const isEnrolled = (courseId) => {
  return enrollments.value.some((e) => e.course_id === courseId)
}

const goTo = (path) => {
  router.push(path)
}

const loadEnrollments = async () => {
  if (!isAuthenticated.value || !isStudent.value) return
  try {
    const response = await api.get('/api/v1/enrollments/me')
    enrollments.value = response.data || []
  } catch (err) {
    console.error('Erro ao carregar matrículas:', err)
  }
}

const loadCourses = async () => {
  loading.value = true
  error.value = null
  try {
    const response = await api.get('/api/v1/courses/')
    courses.value = (response.data || []).filter((c) => c.is_active !== false)
  } catch (err) {
    console.error('Erro ao carregar cursos:', err)
    error.value = 'Não foi possível carregar os cursos.'
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  await loadCourses()
  await loadEnrollments()
})
</script>
