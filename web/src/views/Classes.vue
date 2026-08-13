<template>
  <div class="min-h-screen bg-gray-50">
    <AppNavbar />

    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div class="flex justify-between items-center mb-8">
        <h1 class="text-3xl font-bold text-secondary-900">Turmas</h1>
        <AppButton
          v-if="isAdmin"
          @click="showForm = true"
          class="bg-primary-600 text-white"
        >
          + Nova Turma
        </AppButton>
      </div>

      <!-- Formulário -->
      <AppCard v-if="showForm" class="mb-8">
        <template #header>
          <h2 class="text-xl font-semibold text-secondary-900">{{ editingId ? 'Editar' : 'Nova' }} Turma</h2>
        </template>
        <form @submit.prevent="saveClass" class="space-y-4">
          <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">Curso *</label>
              <select
                v-model="form.course_id"
                class="w-full px-4 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500"
                required
              >
                <option value="">Selecione um curso</option>
                <option v-for="course in courses" :key="course.id" :value="course.id">
                  {{ course.name }}
                </option>
              </select>
            </div>
            <AppInput
              v-model="form.max_students"
              label="Máximo de Alunos"
              type="number"
              placeholder="30"
              required
            />
            <AppInput
              v-model="form.start_date"
              label="Data de Início"
              type="date"
              required
            />
            <AppInput
              v-model="form.end_date"
              label="Data de Término"
              type="date"
              required
            />
            <AppInput
              v-model="form.location"
              label="Local (Presencial)"
              placeholder="Sala 101"
            />
            <AppInput
              v-model="form.ead_link"
              label="Link EAD"
              placeholder="https://..."
            />
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">Status</label>
              <select
                v-model="form.status"
                class="w-full px-4 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500"
              >
                <option value="ABERTA">Aberta</option>
                <option value="EM_ANDAMENTO">Em Andamento</option>
                <option value="CONCLUIDA">Concluída</option>
                <option value="CANCELADA">Cancelada</option>
              </select>
            </div>
          </div>
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">Descrição</label>
            <textarea
              v-model="form.description"
              placeholder="Descrição da turma"
              class="w-full px-4 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500"
              rows="3"
            ></textarea>
          </div>
          <div class="flex gap-2">
            <AppButton type="submit" class="bg-primary-600 text-white">Salvar</AppButton>
            <AppButton type="button" @click="showForm = false" class="bg-gray-300 text-gray-700">Cancelar</AppButton>
          </div>
        </form>
      </AppCard>

      <!-- Lista -->
      <div v-if="loading" class="text-center py-8">
        <p class="text-gray-600">Carregando turmas...</p>
      </div>

      <div v-else-if="classes.length === 0" class="text-center py-8">
        <p class="text-gray-600">Nenhuma turma disponível</p>
      </div>

      <div v-else class="grid grid-cols-1 md:grid-cols-2 gap-6">
        <AppCard v-for="cls in classes" :key="cls.id" class="hover:shadow-lg transition-shadow">
          <template #header>
            <div class="flex justify-between items-start">
              <h3 class="text-lg font-semibold text-secondary-900">{{ getCourseNameById(cls.course_id) }}</h3>
              <span :class="['px-2 py-1 rounded text-xs font-semibold', getStatusColor(cls.status)]">
                {{ formatStatus(cls.status) }}
              </span>
            </div>
          </template>
          <div class="space-y-2 text-sm">
            <p><strong>Período:</strong> {{ formatDate(cls.start_date) }} a {{ formatDate(cls.end_date) }}</p>
            <p><strong>Máx. Alunos:</strong> {{ cls.max_students }}</p>
            <p v-if="cls.location"><strong>Local:</strong> {{ cls.location }}</p>
            <p v-if="cls.ead_link"><strong>Link EAD:</strong> <a :href="cls.ead_link" target="_blank" class="text-primary-600 hover:underline">Acessar</a></p>
            <p v-if="cls.description" class="text-gray-600 mt-3">{{ cls.description }}</p>
          </div>
          <div v-if="isAdmin" class="mt-4 flex gap-2">
            <AppButton @click="editClass(cls)" class="bg-blue-600 text-white text-sm flex-1">Editar</AppButton>
            <AppButton @click="deleteClass(cls.id)" class="bg-red-600 text-white text-sm flex-1">Deletar</AppButton>
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

const classes = ref([])
const courses = ref([])
const loading = ref(false)
const showForm = ref(false)
const editingId = ref(null)
const form = ref({
  course_id: '',
  max_students: 30,
  start_date: '',
  end_date: '',
  location: '',
  ead_link: '',
  status: 'ABERTA',
  description: '',
})

const isAdmin = computed(() => authStore.userRole?.toLowerCase() === 'admin')

const formatDate = (date) => {
  return new Date(date).toLocaleDateString('pt-BR')
}

const formatStatus = (status) => {
  const map = {
    'ABERTA': 'Aberta',
    'EM_ANDAMENTO': 'Em Andamento',
    'CONCLUIDA': 'Concluída',
    'CANCELADA': 'Cancelada'
  }
  return map[status] || status
}

const getStatusColor = (status) => {
  const colors = {
    'ABERTA': 'bg-green-100 text-green-800',
    'EM_ANDAMENTO': 'bg-blue-100 text-blue-800',
    'CONCLUIDA': 'bg-gray-100 text-gray-800',
    'CANCELADA': 'bg-red-100 text-red-800'
  }
  return colors[status] || 'bg-gray-100 text-gray-800'
}

const getCourseNameById = (courseId) => {
  return courses.value.find(c => c.id === courseId)?.name || 'Curso desconhecido'
}

const loadCourses = async () => {
  try {
    const response = await api.get('/api/v1/courses/')
    courses.value = response.data
  } catch (error) {
    console.error('Erro ao carregar cursos:', error)
  }
}

const loadClasses = async () => {
  loading.value = true
  try {
    const response = await api.get('/api/v1/classes/')
    classes.value = response.data
  } catch (error) {
    console.error('Erro ao carregar turmas:', error)
  } finally {
    loading.value = false
  }
}

const saveClass = async () => {
  try {
    const payload = {
      ...form.value,
      instructor_id: authStore.user?.id,
      max_students: Number(form.value.max_students),
      location: form.value.location || null,
      ead_link: form.value.ead_link || null,
      description: form.value.description || null,
    }

    if (editingId.value) {
      // Atualizar só os campos permitidos pelo schema de update
      const updatePayload = {
        start_date: payload.start_date,
        end_date: payload.end_date,
        max_students: payload.max_students,
        location: payload.location,
        ead_link: payload.ead_link,
        description: payload.description,
        status: payload.status,
      }
      await api.put(`/api/v1/classes/${editingId.value}`, updatePayload)
    } else {
      await api.post('/api/v1/classes/', payload)
    }
    resetForm()
    loadClasses()
  } catch (error) {
    console.error('Erro ao salvar turma:', error)
    alert('Erro ao salvar turma: ' + (error.response?.data?.detail || error.message))
  }
}

const editClass = (cls) => {
  editingId.value = cls.id
  form.value = { ...cls }
  showForm.value = true
}

const deleteClass = async (id) => {
  if (confirm('Tem certeza que deseja deletar esta turma?')) {
    try {
      await api.delete(`/api/v1/classes/${id}`)
      loadClasses()
    } catch (error) {
      console.error('Erro ao deletar turma:', error)
      alert('Erro ao deletar turma')
    }
  }
}

const resetForm = () => {
  editingId.value = null
  form.value = {
    course_id: '',
    max_students: 30,
    start_date: '',
    end_date: '',
    location: '',
    ead_link: '',
    status: 'ABERTA',
    description: '',
  }
  showForm.value = false
}

onMounted(() => {
  loadCourses()
  loadClasses()
})
</script>
