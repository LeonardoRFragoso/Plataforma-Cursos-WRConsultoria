<template>
  <div>
    <AppPageHeader title="Alunos" description="Gerencie os alunos cadastrados.">
      <template #actions>
        <AppButton
          v-if="isAdmin"
          @click="showForm = true"
          class="bg-primary-600 text-white"
          data-testid="new-student"
        >
          + Novo Aluno
        </AppButton>
      </template>
    </AppPageHeader>

    <!-- Filters -->
    <div class="flex flex-wrap gap-3 mb-6">
      <div>
        <label class="block text-xs font-medium text-gray-600 mb-1">Origem</label>
        <select v-model="originFilter" class="px-3 py-2 border border-gray-300 rounded-md text-sm">
          <option value="">Todos</option>
          <option value="corporate">Corporativos</option>
          <option value="independent">Individuais</option>
        </select>
      </div>
      <div>
        <label class="block text-xs font-medium text-gray-600 mb-1">Empresa</label>
        <select v-model="companyFilter" class="px-3 py-2 border border-gray-300 rounded-md text-sm">
          <option value="">Todas</option>
          <option v-for="c in companies" :key="c.id" :value="c.id">{{ c.trade_name || c.legal_name }}</option>
        </select>
      </div>
      <div class="flex-1 min-w-[200px]">
        <label class="block text-xs font-medium text-gray-600 mb-1">Buscar</label>
        <input v-model="searchQuery" type="text" placeholder="Nome, CPF ou e-mail..." class="w-full px-3 py-2 border border-gray-300 rounded-md text-sm" />
      </div>
    </div>

    <!-- Form -->
    <AppCard v-if="showForm" class="mb-8">
      <template #header>
        <h2 class="text-xl font-semibold text-secondary-900">{{ editingId ? 'Editar' : 'Novo' }} Aluno</h2>
      </template>
      <form @submit.prevent="saveStudent" class="space-y-4">
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <AppInput v-model="form.full_name" label="Nome Completo *" placeholder="João Silva" required />
          <AppInput v-model="form.email" label="E-mail *" type="email" placeholder="joao@empresa.com" required />
          <AppInput v-model="form.cpf" label="CPF *" placeholder="000.000.000-00" required />
          <AppInput v-model="form.phone" label="Telefone" placeholder="(11) 99999-9999" />
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">Empresa</label>
            <select v-model="form.company_id" class="w-full px-4 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500">
              <option :value="null">Aluno independente (sem empresa)</option>
              <option v-for="c in companies" :key="c.id" :value="c.id">{{ c.trade_name || c.legal_name }}</option>
            </select>
          </div>
          <AppInput v-model="form.city" label="Cidade" placeholder="São Paulo" />
          <AppInput v-model="form.state" label="Estado" placeholder="SP" />
          <AppInput v-model="form.zip_code" label="CEP" placeholder="00000-000" />
          <div v-if="!editingId">
            <label class="block text-sm font-medium text-gray-700 mb-1">Turma</label>
            <select v-model="form.class_id" class="w-full px-4 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500">
              <option value="">Sem matrícula imediata</option>
              <option v-for="cls in availableClasses" :key="cls.id" :value="cls.id">
                {{ getCourseNameById(cls.course_id) }} — {{ new Date(cls.start_date).toLocaleDateString('pt-BR') }} ({{ cls.max_students - enrollmentCountByClass[cls.id] }} vagas)
              </option>
            </select>
            <p class="text-xs text-gray-500 mt-1">Deixe em branco para criar apenas a conta do aluno.</p>
          </div>
        </div>
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">Endereço</label>
          <textarea v-model="form.address" placeholder="Rua, número, complemento" class="w-full px-4 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500" rows="2"></textarea>
        </div>
        <div v-if="!editingId" class="bg-blue-50 border border-blue-200 rounded-md p-3 text-sm text-blue-800">
          Se não informar turma nem senha, o aluno receberá um link de ativação por e-mail para definir sua própria senha.
        </div>
        <div class="flex gap-2">
          <AppButton type="submit" class="bg-primary-600 text-white" :disabled="saving" data-testid="save-student">Salvar</AppButton>
          <AppButton type="button" @click="showForm = false" class="bg-gray-300 text-gray-700" data-testid="cancel-student">Cancelar</AppButton>
        </div>
      </form>
    </AppCard>

    <!-- List -->
    <LoadingState v-if="loading" message="Carregando alunos..." />

    <AppAlert v-else-if="loadError" type="error" closable @close="loadError = ''">
      {{ loadError }}
    </AppAlert>

    <EmptyState
      v-else-if="filteredStudents.length === 0"
      title="Nenhum aluno encontrado"
      description="Ajuste os filtros ou cadastre um novo aluno."
    />

    <div v-else class="overflow-x-auto">
      <table class="w-full border-collapse">
        <thead>
          <tr class="bg-gray-200">
            <th class="px-4 py-2 text-left font-semibold text-gray-700">Aluno</th>
            <th class="px-4 py-2 text-left font-semibold text-gray-700">CPF</th>
            <th class="px-4 py-2 text-left font-semibold text-gray-700">E-mail</th>
            <th class="px-4 py-2 text-left font-semibold text-gray-700">Empresa</th>
            <th class="px-4 py-2 text-left font-semibold text-gray-700">Origem</th>
            <th class="px-4 py-2 text-left font-semibold text-gray-700">Ações</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="student in filteredStudents" :key="student.id" class="border-b hover:bg-gray-50 cursor-pointer" @click="$router.push(`/students/${student.id}`)">
            <td class="px-4 py-2 font-medium">{{ student.full_name || '-' }}</td>
            <td class="px-4 py-2 text-sm text-gray-600">{{ student.cpf }}</td>
            <td class="px-4 py-2 text-sm text-gray-600">{{ student.email || '-' }}</td>
            <td class="px-4 py-2 text-sm">{{ getCompanyName(student.company_id) || '—' }}</td>
            <td class="px-4 py-2">
              <span :class="student.company_id ? 'bg-blue-100 text-blue-800' : 'bg-gray-100 text-gray-700'" class="px-2 py-0.5 rounded text-xs font-medium">
                {{ student.company_id ? 'Corporativo' : 'Individual' }}
              </span>
            </td>
            <td class="px-4 py-2 space-x-2" @click.stop>
              <AppButton @click="editStudent(student)" class="bg-blue-600 text-white text-xs px-2 py-1" data-testid="edit-student">Editar</AppButton>
              <AppButton @click="deleteStudent(student)" class="bg-red-600 text-white text-xs px-2 py-1" data-testid="delete-student">Excluir</AppButton>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <ConfirmDialog
      v-model="showDeleteConfirm"
      title="Excluir aluno"
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
import AppPageHeader from '../components/AppPageHeader.vue'
import AppCard from '../components/AppCard.vue'
import AppButton from '../components/AppButton.vue'
import AppInput from '../components/AppInput.vue'
import AppAlert from '../components/AppAlert.vue'
import EmptyState from '../components/EmptyState.vue'
import LoadingState from '../components/LoadingState.vue'
import ConfirmDialog from '../components/ConfirmDialog.vue'
import { useToast } from '../composables/useToast'

const { success: toastSuccess, error: toastError } = useToast()
const authStore = useAuthStore()

const students = ref([])
const classes = ref([])
const courses = ref([])
const enrollments = ref([])
const companies = ref([])
const loading = ref(false)
const showForm = ref(false)
const editingId = ref(null)
const showDeleteConfirm = ref(false)
const deleting = ref(false)
const pendingDeleteId = ref(null)
const pendingDeleteName = ref('')
const saving = ref(false)
const loadError = ref('')

// Filters
const originFilter = ref('')
const companyFilter = ref('')
const searchQuery = ref('')

const form = ref({
  full_name: '',
  email: '',
  cpf: '',
  phone: '',
  company_id: null,
  address: '',
  city: '',
  state: '',
  zip_code: '',
  class_id: '',
})

const isAdmin = computed(() => authStore.userRole?.toLowerCase() === 'admin' || authStore.userRole?.toLowerCase() === 'super_admin')

const filteredStudents = computed(() => {
  let result = students.value
  if (originFilter.value === 'corporate') {
    result = result.filter(s => s.company_id)
  } else if (originFilter.value === 'independent') {
    result = result.filter(s => !s.company_id)
  }
  if (companyFilter.value) {
    result = result.filter(s => s.company_id === companyFilter.value)
  }
  if (searchQuery.value) {
    const q = searchQuery.value.toLowerCase()
    result = result.filter(s =>
      (s.full_name || '').toLowerCase().includes(q) ||
      (s.cpf || '').includes(q) ||
      (s.email || '').toLowerCase().includes(q)
    )
  }
  return result
})

const getCourseNameById = (courseId) => {
  return courses.value.find(c => c.id === courseId)?.name || 'Curso desconhecido'
}

const getCompanyName = (companyId) => {
  if (!companyId) return null
  return companies.value.find(c => c.id === companyId)?.trade_name || companies.value.find(c => c.id === companyId)?.legal_name
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

const deleteMessage = computed(() => {
  return `Excluir o aluno "${pendingDeleteName.value}"? Esta ação não pode ser desfeita.`
})

const loadStudents = async () => {
  loading.value = true
  loadError.value = ''
  try {
    const response = await api.get('/api/v1/students/')
    students.value = response.data
  } catch (error) {
    loadError.value = 'Erro ao carregar alunos. Tente novamente.'
  } finally {
    loading.value = false
  }
}

const loadClasses = async () => {
  try { const response = await api.get('/api/v1/classes/'); classes.value = response.data } catch (e) { /* silent */ }
}

const loadEnrollments = async () => {
  try { const response = await api.get('/api/v1/enrollments/'); enrollments.value = response.data } catch (e) { /* silent */ }
}

const loadCourses = async () => {
  try { const response = await api.get('/api/v1/courses/'); courses.value = response.data } catch (e) { /* silent */ }
}

const loadCompanies = async () => {
  try { const response = await api.get('/api/v1/companies/'); companies.value = response.data } catch (e) { /* silent */ }
}

const saveStudent = async () => {
  saving.value = true
  try {
    if (editingId.value) {
      const updatePayload = {
        phone: form.value.phone,
        company_id: form.value.company_id,
        address: form.value.address,
        city: form.value.city,
        state: form.value.state,
        zip_code: form.value.zip_code,
      }
      await api.put(`/api/v1/students/${editingId.value}`, updatePayload)
      toastSuccess('Aluno atualizado com sucesso!')
    } else {
      const createPayload = { ...form.value }
      if (!createPayload.class_id) delete createPayload.class_id
      const response = await api.post('/api/v1/students/', createPayload)
      if (response.data.temp_password) {
        toastSuccess(`Aluno cadastrado! Senha temporária: ${response.data.temp_password}`)
      } else if (response.data.activation_token) {
        const link = `${window.location.origin}/redefinir-senha?token=${response.data.activation_token}&activation=1`
        toastSuccess('Aluno cadastrado! Link de ativação gerado.')
        navigator.clipboard.writeText(link)
      } else {
        toastSuccess('Aluno cadastrado com sucesso!')
      }
    }
    resetForm()
    await loadStudents()
    await loadEnrollments()
  } catch (error) {
    const detail = error.response?.data?.detail
    const message = typeof detail === 'object' ? JSON.stringify(detail) : (detail || error.message)
    toastError('Erro ao salvar aluno: ' + message)
  } finally {
    saving.value = false
  }
}

const editStudent = (student) => {
  editingId.value = student.id
  form.value = {
    full_name: student.full_name,
    email: student.email,
    cpf: student.cpf,
    phone: student.phone,
    company_id: student.company_id || null,
    address: student.address,
    city: student.city,
    state: student.state,
    zip_code: student.zip_code,
    class_id: '',
  }
  showForm.value = true
}

const deleteStudent = (student) => {
  pendingDeleteId.value = student.id
  pendingDeleteName.value = student.full_name
  showDeleteConfirm.value = true
}

const doDelete = async () => {
  deleting.value = true
  try {
    await api.delete(`/api/v1/students/${pendingDeleteId.value}`)
    await loadStudents()
    showDeleteConfirm.value = false
    toastSuccess('Aluno excluído com sucesso!')
  } catch (error) {
    toastError('Erro ao deletar aluno')
  } finally {
    deleting.value = false
    pendingDeleteId.value = null
    pendingDeleteName.value = ''
  }
}

const resetForm = () => {
  editingId.value = null
  form.value = {
    full_name: '',
    email: '',
    cpf: '',
    phone: '',
    company_id: null,
    address: '',
    city: '',
    state: '',
    zip_code: '',
    class_id: '',
  }
  showForm.value = false
}

onMounted(async () => {
  await Promise.all([loadStudents(), loadClasses(), loadCourses(), loadEnrollments(), loadCompanies()])
})
</script>
