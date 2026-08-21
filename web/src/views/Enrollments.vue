<template>
  <div class="min-h-screen bg-gray-50">
    <AppNavbar />

    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div class="flex justify-between items-center mb-8">
        <h1 class="text-3xl font-bold text-secondary-900">Matrículas</h1>
        <AppButton
          v-if="isAdmin"
          @click="showForm = true"
          class="bg-primary-600 text-white"
          data-testid="btn-new-enrollment"
        >
          + Nova Matrícula
        </AppButton>
      </div>

      <!-- Formulário -->
      <AppCard v-if="showForm" class="mb-8">
        <template #header>
          <h2 class="text-xl font-semibold text-secondary-900">{{ editingId ? 'Editar' : 'Nova' }} Matrícula</h2>
        </template>
        <form @submit.prevent="saveEnrollment" class="space-y-4">
          <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">Aluno *</label>
              <select
                v-model="form.student_id"
                class="w-full px-4 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500"
                required
              >
                <option value="">Selecione um aluno</option>
                <option v-for="student in students" :key="student.id" :value="student.id">
                  {{ student.full_name }} ({{ student.cpf }})
                </option>
              </select>
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">Turma *</label>
              <select
                v-model="form.class_id"
                class="w-full px-4 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500"
                required
              >
                <option value="">Selecione uma turma</option>
                <option v-for="cls in classes" :key="cls.id" :value="cls.id">
                  {{ getCourseNameById(cls.course_id) }} - {{ formatDate(cls.start_date) }}
                </option>
              </select>
            </div>
            <AppInput
              v-model.number="form.price"
              label="Preço"
              type="number"
              step="0.01"
              required
            />
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">Status</label>
              <select
                v-model="form.status"
                class="w-full px-4 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500"
              >
                <option value="PENDENTE">Pendente</option>
                <option value="CONFIRMADA">Confirmada</option>
                <option value="CANCELADA">Cancelada</option>
                <option value="CONCLUIDA">Concluída</option>
              </select>
            </div>
          </div>
          <div class="flex gap-2">
            <AppButton type="submit" class="bg-primary-600 text-white" :disabled="saving" data-testid="btn-save-enrollment">
              {{ saving ? 'Salvando...' : 'Salvar' }}
            </AppButton>
            <AppButton type="button" @click="showForm = false" class="bg-gray-300 text-gray-700" data-testid="btn-cancel-enrollment">Cancelar</AppButton>
          </div>
        </form>
      </AppCard>

      <!-- Erro de carregamento -->
      <AppAlert
        v-if="loadError"
        type="error"
        closable
        @close="loadError = ''"
        class="mb-8"
      >
        {{ loadError }}
      </AppAlert>

      <!-- Lista -->
      <LoadingState v-if="loading" message="Carregando matrículas..." />

      <EmptyState
        v-else-if="enrollments.length === 0"
        title="Nenhuma matrícula cadastrada"
        description="Clique em 'Nova Matrícula' para criar a primeira matrícula."
      />

      <div v-else class="overflow-x-auto">
        <table class="w-full border-collapse">
          <thead>
            <tr class="bg-gray-200">
              <th class="px-4 py-2 text-left font-semibold text-gray-700">Aluno</th>
              <th class="px-4 py-2 text-left font-semibold text-gray-700">Curso</th>
              <th class="px-4 py-2 text-left font-semibold text-gray-700">Turma</th>
              <th class="px-4 py-2 text-left font-semibold text-gray-700">Preço</th>
              <th class="px-4 py-2 text-left font-semibold text-gray-700">Status</th>
              <th class="px-4 py-2 text-left font-semibold text-gray-700">Data</th>
              <th class="px-4 py-2 text-left font-semibold text-gray-700">Ações</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="enrollment in enrollments" :key="enrollment.id" class="border-b hover:bg-gray-50">
              <td class="px-4 py-2">{{ getStudentNameById(enrollment.student_id) }}</td>
              <td class="px-4 py-2">{{ getCourseNameByClassId(enrollment.class_id) }}</td>
              <td class="px-4 py-2">{{ getClassNameById(enrollment.class_id) }}</td>
              <td class="px-4 py-2">R$ {{ formatPrice(enrollment.price) }}</td>
              <td class="px-4 py-2">
                <span :class="['px-2 py-1 rounded text-xs font-semibold', getStatusColor(enrollment.status)]">
                  {{ formatStatus(enrollment.status) }}
                </span>
              </td>
              <td class="px-4 py-2">{{ formatDate(enrollment.enrollment_date) }}</td>
              <td class="px-4 py-2 space-x-2">
                <AppButton @click="editEnrollment(enrollment)" class="bg-blue-600 text-white text-xs px-2 py-1" data-testid="btn-edit-enrollment">Editar</AppButton>
                <AppButton @click="deleteEnrollment(enrollment)" class="bg-red-600 text-white text-xs px-2 py-1" data-testid="btn-delete-enrollment">Deletar</AppButton>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <ConfirmDialog
      v-model="showDeleteConfirm"
      title="Excluir matrícula"
      :message="deleteMessage"
      confirmText="Excluir"
      cancelText="Cancelar"
      :danger="true"
      :loading="deleting"
      @confirm="doDelete"
    />
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
import AppAlert from '../components/AppAlert.vue'
import EmptyState from '../components/EmptyState.vue'
import LoadingState from '../components/LoadingState.vue'
import ConfirmDialog from '../components/ConfirmDialog.vue'
import { useToast } from '../composables/useToast'

const { error: toastError } = useToast()

const authStore = useAuthStore()

const enrollments = ref([])
const students = ref([])
const classes = ref([])
const courses = ref([])
const loading = ref(false)
const showForm = ref(false)
const editingId = ref(null)
const form = ref({
  student_id: '',
  class_id: '',
  price: 0,
  status: 'PENDENTE',
})

const showDeleteConfirm = ref(false)
const deleting = ref(false)
const pendingDeleteId = ref(null)
const pendingDeleteName = ref('')
const saving = ref(false)
const loadError = ref('')

const isAdmin = computed(() => authStore.userRole?.toLowerCase() === 'admin' || authStore.userRole?.toLowerCase() === 'super_admin')

const deleteMessage = computed(() =>
  `Excluir a matrícula de "${pendingDeleteName.value}"? Esta ação não pode ser desfeita.`
)

const formatDate = (date) => {
  return new Date(date).toLocaleDateString('pt-BR')
}

const formatPrice = (price) => {
  return parseFloat(price).toFixed(2).replace('.', ',')
}

const formatStatus = (status) => {
  const map = {
    'PENDENTE': 'Pendente',
    'CONFIRMADA': 'Confirmada',
    'CANCELADA': 'Cancelada',
    'CONCLUIDA': 'Concluída'
  }
  return map[status] || status
}

const getStatusColor = (status) => {
  const colors = {
    'PENDENTE': 'bg-yellow-100 text-yellow-800',
    'CONFIRMADA': 'bg-green-100 text-green-800',
    'CANCELADA': 'bg-red-100 text-red-800',
    'CONCLUIDA': 'bg-blue-100 text-blue-800'
  }
  return colors[status] || 'bg-gray-100 text-gray-800'
}

const getStudentNameById = (id) => {
  const student = students.value.find(s => s.id === id)
  if (!student) return 'Aluno desconhecido'
  return `${student.full_name} (${student.cpf})`
}

const getCourseNameById = (id) => {
  return courses.value.find(c => c.id === id)?.name || 'Curso desconhecido'
}

const getCourseNameByClassId = (classId) => {
  const cls = classes.value.find(c => c.id === classId)
  if (!cls) return 'Curso desconhecido'
  return getCourseNameById(cls.course_id)
}

const getClassNameById = (classId) => {
  const cls = classes.value.find(c => c.id === classId)
  if (!cls) return 'Turma desconhecida'
  return `${getCourseNameById(cls.course_id)} - ${formatDate(cls.start_date)}`
}

const loadEnrollments = async () => {
  loading.value = true
  loadError.value = ''
  try {
    const response = await api.get('/api/v1/enrollments/')
    enrollments.value = response.data
  } catch (error) {
    console.error('Erro ao carregar matrículas:', error)
    loadError.value = 'Erro ao carregar matrículas. Tente novamente.'
  } finally {
    loading.value = false
  }
}

const loadDependencies = async () => {
  try {
    const [studentsRes, classesRes, coursesRes] = await Promise.all([
      api.get('/api/v1/students/'),
      api.get('/api/v1/classes/'),
      api.get('/api/v1/courses/')
    ])
    students.value = studentsRes.data
    classes.value = classesRes.data
    courses.value = coursesRes.data
  } catch (error) {
    console.error('Erro ao carregar dependências:', error)
  }
}

const saveEnrollment = async () => {
  saving.value = true
  try {
    if (editingId.value) {
      await api.put(`/api/v1/enrollments/${editingId.value}`, form.value)
    } else {
      await api.post('/api/v1/enrollments/', form.value)
    }
    resetForm()
    loadEnrollments()
  } catch (error) {
    console.error('Erro ao salvar matrícula:', error)
    toastError('Erro ao salvar matrícula: ' + (error.response?.data?.detail || error.message))
  } finally {
    saving.value = false
  }
}

const editEnrollment = (enrollment) => {
  editingId.value = enrollment.id
  form.value = { ...enrollment }
  showForm.value = true
}

const deleteEnrollment = (enrollment) => {
  pendingDeleteId.value = enrollment.id
  pendingDeleteName.value = getStudentNameById(enrollment.student_id)
  showDeleteConfirm.value = true
}

const doDelete = async () => {
  if (pendingDeleteId.value === null) return
  deleting.value = true
  try {
    await api.delete(`/api/v1/enrollments/${pendingDeleteId.value}`)
    loadEnrollments()
  } catch (error) {
    console.error('Erro ao deletar matrícula:', error)
    toastError('Erro ao deletar matrícula')
  } finally {
    deleting.value = false
    showDeleteConfirm.value = false
    pendingDeleteId.value = null
    pendingDeleteName.value = ''
  }
}

const resetForm = () => {
  editingId.value = null
  form.value = {
    student_id: '',
    class_id: '',
    price: 0,
    status: 'PENDENTE',
  }
  showForm.value = false
}

onMounted(() => {
  loadDependencies()
  loadEnrollments()
})
</script>
