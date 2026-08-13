<template>
  <div class="min-h-screen bg-gray-50">
    <nav class="bg-white shadow-sm border-b border-gray-200">
      <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4 flex justify-between items-center">
        <router-link to="/dashboard" class="flex items-center space-x-2">
          <div class="text-2xl font-bold text-primary-600">WR</div>
          <div class="text-sm text-gray-600">Consultoria</div>
        </router-link>
        <button @click="handleLogout" class="text-red-600 hover:text-red-700 transition-colors">Sair</button>
      </div>
    </nav>

    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div class="flex justify-between items-center mb-8">
        <h1 class="text-3xl font-bold text-secondary-900">Cursos</h1>
        <button
          @click="showForm = true"
          class="bg-primary-600 text-white px-4 py-2 rounded-md hover:bg-primary-700 transition-colors"
        >
          + Novo Curso
        </button>
      </div>

      <div v-if="showForm" class="bg-white p-6 rounded-lg shadow-md mb-8 border border-gray-200">
        <h2 class="text-xl font-semibold text-secondary-900 mb-4">{{ editingId ? 'Editar' : 'Novo' }} Curso</h2>
        <form @submit.prevent="saveCourse" class="space-y-4">
          <div class="grid grid-cols-2 gap-4">
            <input
              v-model="form.code"
              placeholder="Código (ex: NR-10)"
              class="px-4 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500"
              required
            />
            <input
              v-model="form.name"
              placeholder="Nome do Curso"
              class="px-4 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500"
              required
            />
            <input
              v-model="form.category"
              placeholder="Categoria"
              class="px-4 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500"
              required
            />
            <input
              v-model.number="form.carga_horaria"
              type="number"
              placeholder="Carga Horária"
              class="px-4 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500"
              required
            />
            <input
              v-model.number="form.price"
              type="number"
              placeholder="Preço"
              step="0.01"
              class="px-4 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500"
              required
            />
            <select
              v-model="form.modality"
              class="px-4 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500"
              required
            >
              <option value="presencial">Presencial</option>
              <option value="ead">EAD</option>
              <option value="semipresencial">Semipresencial</option>
            </select>
          </div>
          <textarea
            v-model="form.description"
            placeholder="Descrição"
            class="w-full px-4 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500"
            rows="3"
          ></textarea>
          <div class="flex gap-2">
            <button type="submit" class="bg-primary-600 text-white px-4 py-2 rounded-md hover:bg-primary-700 transition-colors">
              Salvar
            </button>
            <button
              type="button"
              @click="showForm = false"
              class="bg-gray-300 text-gray-700 px-4 py-2 rounded-md hover:bg-gray-400 transition-colors"
            >
              Cancelar
            </button>
          </div>
        </form>
      </div>

      <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div v-for="course in courses" :key="course.id" class="bg-white p-6 rounded-lg shadow-md border border-gray-200 hover:shadow-lg transition-shadow">
          <h3 class="text-lg font-semibold text-secondary-900">{{ course.name }}</h3>
          <p class="text-gray-600 text-sm">{{ course.code }}</p>
          <p class="text-gray-600 mt-2">{{ course.description }}</p>
          <div class="mt-4 flex justify-between items-center">
            <span class="text-primary-600 font-semibold">R$ {{ course.price }}</span>
            <div class="space-x-2">
              <button
                @click="editCourse(course)"
                class="text-blue-600 hover:text-blue-700"
              >
                Editar
              </button>
              <button
                @click="deleteCourse(course.id)"
                class="text-red-600 hover:text-red-700"
              >
                Deletar
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import api from '../api/client'

const router = useRouter()
const authStore = useAuthStore()

const courses = ref([])
const showForm = ref(false)
const editingId = ref(null)
const form = ref({
  code: '',
  name: '',
  category: '',
  carga_horaria: 0,
  price: 0,
  modality: 'presencial',
  description: '',
})

const loadCourses = async () => {
  try {
    const response = await api.get('/courses/')
    courses.value = response.data
  } catch (error) {
    console.error('Erro ao carregar cursos:', error)
  }
}

const saveCourse = async () => {
  try {
    if (editingId.value) {
      await api.put(`/courses/${editingId.value}`, form.value)
    } else {
      await api.post('/courses/', form.value)
    }
    resetForm()
    loadCourses()
  } catch (error) {
    console.error('Erro ao salvar curso:', error)
  }
}

const editCourse = (course) => {
  editingId.value = course.id
  form.value = { ...course }
  showForm.value = true
}

const deleteCourse = async (id) => {
  if (confirm('Tem certeza?')) {
    try {
      await api.delete(`/courses/${id}`)
      loadCourses()
    } catch (error) {
      console.error('Erro ao deletar curso:', error)
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
    modality: 'presencial',
    description: '',
  }
  showForm.value = false
}

const handleLogout = () => {
  authStore.logout()
  router.push('/login')
}

onMounted(loadCourses)
</script>
