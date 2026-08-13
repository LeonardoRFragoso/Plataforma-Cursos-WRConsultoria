<template>
  <div class="min-h-screen bg-gray-50">
    <AppNavbar />

    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div class="flex justify-between items-center mb-8">
        <h1 class="text-3xl font-bold text-secondary-900">Cursos</h1>
        <AppButton
          v-if="isAdmin"
          @click="showForm = true"
          class="bg-primary-600 text-white"
        >
          + Novo Curso
        </AppButton>
      </div>

      <!-- Formulário de Curso -->
      <AppCard v-if="showForm" class="mb-8">
        <template #header>
          <h2 class="text-xl font-semibold text-secondary-900">{{ editingId ? 'Editar' : 'Novo' }} Curso</h2>
        </template>
        <form @submit.prevent="saveCourse" class="space-y-4">
          <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
            <AppInput
              v-model="form.code"
              label="Código (ex: NR-10)"
              placeholder="NR-10"
              required
            />
            <AppInput
              v-model="form.name"
              label="Nome do Curso"
              placeholder="Nome do Curso"
              required
            />
            <AppInput
              v-model="form.category"
              label="Categoria"
              placeholder="Categoria"
              required
            />
            <AppInput
              v-model.number="form.carga_horaria"
              label="Carga Horária"
              type="number"
              placeholder="40"
              required
            />
            <AppInput
              v-model.number="form.price"
              label="Preço (R$)"
              type="number"
              placeholder="0.00"
              step="0.01"
              required
            />
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">Modalidade</label>
              <select
                v-model="form.modality"
                class="w-full px-4 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500"
                required
              >
                <option value="PRESENCIAL">Presencial</option>
                <option value="EAD">EAD</option>
                <option value="SEMIPRESENCIAL">Semipresencial</option>
              </select>
            </div>
          </div>
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">Descrição</label>
            <textarea
              v-model="form.description"
              placeholder="Descrição do curso"
              class="w-full px-4 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500"
              rows="3"
            ></textarea>
          </div>
          <div class="flex gap-2">
            <AppButton type="submit" class="bg-primary-600 text-white">
              Salvar
            </AppButton>
            <AppButton
              type="button"
              @click="showForm = false"
              class="bg-gray-300 text-gray-700"
            >
              Cancelar
            </AppButton>
          </div>
        </form>
      </AppCard>

      <!-- Lista de Cursos -->
      <div v-if="loading" class="text-center py-8">
        <p class="text-gray-600">Carregando cursos...</p>
      </div>

      <div v-else-if="courses.length === 0" class="text-center py-8">
        <p class="text-gray-600">Nenhum curso disponível</p>
      </div>

      <div v-else class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        <AppCard v-for="course in courses" :key="course.id" class="hover:shadow-lg transition-shadow">
          <template #header>
            <h3 class="text-lg font-semibold text-secondary-900">{{ course.name }}</h3>
          </template>
          <div class="space-y-2 text-sm">
            <p><strong>Código:</strong> {{ course.code }}</p>
            <p><strong>Categoria:</strong> {{ course.category }}</p>
            <p><strong>Carga Horária:</strong> {{ course.carga_horaria }}h</p>
            <p><strong>Modalidade:</strong> {{ formatModality(course.modality) }}</p>
            <p><strong>Preço:</strong> R$ {{ formatPrice(course.price) }}</p>
            <p v-if="course.description" class="text-gray-600 mt-3">{{ course.description }}</p>
          </div>
          <div v-if="isAdmin" class="mt-4 flex gap-2">
            <AppButton
              @click="editCourse(course)"
              class="bg-blue-600 text-white text-sm flex-1"
            >
              Editar
            </AppButton>
            <AppButton
              @click="deleteCourse(course.id)"
              class="bg-red-600 text-white text-sm flex-1"
            >
              Deletar
            </AppButton>
          </div>
        </AppCard>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { useAuthStore } from '../stores/auth'
import api from '../api/client'
import AppNavbar from '../components/AppNavbar.vue'
import AppCard from '../components/AppCard.vue'
import AppButton from '../components/AppButton.vue'
import AppInput from '../components/AppInput.vue'

const authStore = useAuthStore()

const courses = ref([])
const loading = ref(false)
const showForm = ref(false)
const editingId = ref(null)
const form = ref({
  code: '',
  name: '',
  category: '',
  carga_horaria: 0,
  price: 0,
  modality: 'PRESENCIAL',
  description: '',
})

const isAdmin = computed(() => authStore.userRole?.toLowerCase() === 'admin')

const formatModality = (modality) => {
  const map = {
    'PRESENCIAL': 'Presencial',
    'EAD': 'EAD',
    'SEMIPRESENCIAL': 'Semipresencial'
  }
  return map[modality] || modality
}

const formatPrice = (price) => {
  return parseFloat(price).toFixed(2).replace('.', ',')
}

const loadCourses = async () => {
  loading.value = true
  try {
    const response = await api.get('/api/v1/courses/')
    courses.value = response.data
  } catch (error) {
    console.error('Erro ao carregar cursos:', error)
  } finally {
    loading.value = false
  }
}

const saveCourse = async () => {
  try {
    if (editingId.value) {
      await api.put(`/api/v1/courses/${editingId.value}`, form.value)
    } else {
      await api.post('/api/v1/courses/', form.value)
    }
    resetForm()
    loadCourses()
  } catch (error) {
    console.error('Erro ao salvar curso:', error)
    alert('Erro ao salvar curso: ' + (error.response?.data?.detail || error.message))
  }
}

const editCourse = (course) => {
  editingId.value = course.id
  form.value = { ...course }
  showForm.value = true
}

const deleteCourse = async (id) => {
  if (confirm('Tem certeza que deseja deletar este curso?')) {
    try {
      await api.delete(`/api/v1/courses/${id}`)
      loadCourses()
    } catch (error) {
      console.error('Erro ao deletar curso:', error)
      alert('Erro ao deletar curso')
    }
  }
}

const resetForm = () => {
  editingId.value = null
  form.value = {
    code: '',
    name: '',
    category: '',
    carga_horaria: 0,
    price: 0,
    modality: 'PRESENCIAL',
    description: '',
  }
  showForm.value = false
}

onMounted(loadCourses)
</script>
