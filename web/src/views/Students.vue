<template>
  <div class="min-h-screen bg-gray-50">
    <AppNavbar />

    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div class="flex justify-between items-center mb-8">
        <h1 class="text-3xl font-bold text-secondary-900">Alunos</h1>
        <AppButton
          v-if="isAdmin"
          @click="showForm = true"
          class="bg-primary-600 text-white"
        >
          + Novo Aluno
        </AppButton>
      </div>

      <!-- Formulário -->
      <AppCard v-if="showForm" class="mb-8">
        <template #header>
          <h2 class="text-xl font-semibold text-secondary-900">{{ editingId ? 'Editar' : 'Novo' }} Aluno</h2>
        </template>
        <form @submit.prevent="saveStudent" class="space-y-4">
          <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
            <AppInput
              v-model="form.full_name"
              label="Nome Completo *"
              placeholder="João Silva"
              required
            />
            <AppInput
              v-model="form.email"
              label="E-mail *"
              type="email"
              placeholder="joao@empresa.com"
              required
            />
            <AppInput
              v-model="form.cpf"
              label="CPF *"
              placeholder="000.000.000-00"
              required
            />
            <AppInput
              v-model="form.password"
              label="Senha Inicial"
              type="password"
              placeholder="Deixe em branco para gerar senha temporária"
            />
            <AppInput
              v-model="form.phone"
              label="Telefone"
              placeholder="(11) 99999-9999"
            />
            <AppInput
              v-model="form.company"
              label="Empresa"
              placeholder="Nome da empresa"
            />
            <AppInput
              v-model="form.city"
              label="Cidade"
              placeholder="São Paulo"
            />
            <AppInput
              v-model="form.state"
              label="Estado"
              placeholder="SP"
            />
            <AppInput
              v-model="form.zip_code"
              label="CEP"
              placeholder="00000-000"
            />
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">Turma *</label>
              <select
                v-if="availableClasses.length > 0"
                v-model="form.class_id"
                class="w-full px-4 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500"
                :required="!editingId"
              >
                <option value="">Selecione uma turma</option>
                <option v-for="cls in availableClasses" :key="cls.id" :value="cls.id">
                  {{ getCourseNameById(cls.course_id) }} — {{ new Date(cls.start_date).toLocaleDateString('pt-BR') }} a {{ new Date(cls.end_date).toLocaleDateString('pt-BR') }} ({{ cls.max_students - enrollmentCountByClass[cls.id] }} vagas)
                </option>
              </select>
              <p v-else class="text-sm text-red-600">Nenhuma turma elegível disponível</p>
            </div>
          </div>
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">Endereço</label>
            <textarea
              v-model="form.address"
              placeholder="Rua, número, complemento"
              class="w-full px-4 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500"
              rows="2"
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
        <p class="text-gray-600">Carregando alunos...</p>
      </div>

      <div v-else-if="students.length === 0" class="text-center py-8">
        <p class="text-gray-600">Nenhum aluno cadastrado</p>
      </div>

      <div v-else class="overflow-x-auto">
        <table class="w-full border-collapse">
          <thead>
            <tr class="bg-gray-200">
              <th class="px-4 py-2 text-left font-semibold text-gray-700">Nome</th>
              <th class="px-4 py-2 text-left font-semibold text-gray-700">E-mail</th>
              <th class="px-4 py-2 text-left font-semibold text-gray-700">CPF</th>
              <th class="px-4 py-2 text-left font-semibold text-gray-700">Telefone</th>
              <th class="px-4 py-2 text-left font-semibold text-gray-700">Empresa</th>
              <th class="px-4 py-2 text-left font-semibold text-gray-700">Ações</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="student in students" :key="student.id" class="border-b hover:bg-gray-50">
              <td class="px-4 py-2">{{ student.full_name || '-' }}</td>
              <td class="px-4 py-2">{{ student.email || '-' }}</td>
              <td class="px-4 py-2">{{ student.cpf }}</td>
              <td class="px-4 py-2">{{ student.phone || '-' }}</td>
              <td class="px-4 py-2">{{ student.company || '-' }}</td>
              <td class="px-4 py-2 space-x-2">
                <AppButton @click="editStudent(student)" class="bg-blue-600 text-white text-xs px-2 py-1">Editar</AppButton>
                <AppButton @click="deleteStudent(student.id)" class="bg-red-600 text-white text-xs px-2 py-1">Deletar</AppButton>
              </td>
            </tr>
          </tbody>
        </table>
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

const students = ref([])
const classes = ref([])
const courses = ref([])
const enrollments = ref([])
const loading = ref(false)
const showForm = ref(false)
const editingId = ref(null)
const form = ref({
  full_name: '',
  email: '',
  cpf: '',
  password: '',
  phone: '',
  company: '',
  address: '',
  city: '',
  state: '',
  zip_code: '',
  class_id: '',
})

const isAdmin = computed(() => authStore.userRole?.toLowerCase() === 'admin')

const getCourseNameById = (courseId) => {
  return courses.value.find(c => c.id === courseId)?.name || 'Curso desconhecido'
}

const enrollmentCountByClass = computed(() => {
  const counts = {}
  for (const enrollment of enrollments.value) {
    if (enrollment.status === 'PENDENTE' || enrollment.status === 'CONFIRMADA') {
      counts[enrollment.class_id] = (counts[enrollment.class_id] || 0) + 1
    }
  }
  return counts
})

const availableClasses = computed(() => {
  return classes.value.filter((cls) => {
    if (cls.status !== 'ABERTA') return false
    const course = courses.value.find(c => c.id === cls.course_id)
    if (!course || !course.is_active) return false
    const count = enrollmentCountByClass.value[cls.id] || 0
    return count < cls.max_students
  })
})

const loadStudents = async () => {
  loading.value = true
  try {
    const response = await api.get('/api/v1/students/')
    students.value = response.data
  } catch (error) {
    console.error('Erro ao carregar alunos:', error)
  } finally {
    loading.value = false
  }
}

const loadClasses = async () => {
  try {
    const response = await api.get('/api/v1/classes/')
    classes.value = response.data
  } catch (error) {
    console.error('Erro ao carregar turmas:', error)
  }
}

const loadEnrollments = async () => {
  try {
    const response = await api.get('/api/v1/enrollments/')
    enrollments.value = response.data
  } catch (error) {
    console.error('Erro ao carregar matrículas:', error)
  }
}

const loadCourses = async () => {
  try {
    const response = await api.get('/api/v1/courses/')
    courses.value = response.data
  } catch (error) {
    console.error('Erro ao carregar cursos:', error)
  }
}

const saveStudent = async () => {
  try {
    if (editingId.value) {
      const updatePayload = {
        phone: form.value.phone,
        company: form.value.company,
        address: form.value.address,
        city: form.value.city,
        state: form.value.state,
        zip_code: form.value.zip_code,
      }
      await api.put(`/api/v1/students/${editingId.value}`, updatePayload)
    } else {
      if (!form.value.class_id) {
        alert('Selecione uma turma elegível para o aluno')
        return
      }
      const createPayload = { ...form.value }
      const response = await api.post('/api/v1/students/', createPayload)
      if (response.data.temp_password) {
        alert(`Aluno cadastrado! Senha temporária: ${response.data.temp_password}`)
      }
    }
    resetForm()
    await loadStudents()
    await loadEnrollments()
  } catch (error) {
    console.error('Erro ao salvar aluno:', error)
    const detail = error.response?.data?.detail
    const message = typeof detail === 'object' ? JSON.stringify(detail) : (detail || error.message)
    alert('Erro ao salvar aluno: ' + message)
  }
}

const editStudent = (student) => {
  editingId.value = student.id
  form.value = {
    full_name: student.full_name,
    email: student.email,
    cpf: student.cpf,
    password: '',
    phone: student.phone,
    company: student.company,
    address: student.address,
    city: student.city,
    state: student.state,
    zip_code: student.zip_code,
    class_id: '',
  }
  showForm.value = true
}

const deleteStudent = async (id) => {
  if (confirm('Tem certeza que deseja deletar este aluno?')) {
    try {
      await api.delete(`/api/v1/students/${id}`)
      loadStudents()
    } catch (error) {
      console.error('Erro ao deletar aluno:', error)
      alert('Erro ao deletar aluno')
    }
  }
}

const resetForm = () => {
  editingId.value = null
  form.value = {
    full_name: '',
    email: '',
    cpf: '',
    password: '',
    phone: '',
    company: '',
    address: '',
    city: '',
    state: '',
    zip_code: '',
    class_id: '',
  }
  showForm.value = false
}

onMounted(async () => {
  await Promise.all([loadStudents(), loadClasses(), loadCourses(), loadEnrollments()])
})
</script>
