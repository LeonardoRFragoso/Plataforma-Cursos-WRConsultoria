<template>
  <div>
    <!-- Header -->
    <div class="mb-6">
      <button @click="$router.push('/companies')" class="text-sm text-gray-600 hover:text-gray-900 mb-2">
        ← Voltar para Empresas
      </button>
      <div v-if="company" class="flex items-start justify-between">
        <div>
          <h1 class="text-2xl font-bold text-secondary-900">{{ company.trade_name || company.legal_name }}</h1>
          <p class="text-sm text-gray-600" v-if="company.trade_name">{{ company.legal_name }}</p>
          <p class="text-sm text-gray-500 mt-1">CNPJ: {{ formatCnpj(company.cnpj) }}</p>
          <div v-if="company.rh_name || company.rh_email" class="text-sm text-gray-600 mt-1">
            <span v-if="company.rh_name">RH: {{ company.rh_name }}</span>
            <span v-if="company.rh_email" class="ml-2">{{ company.rh_email }}</span>
          </div>
        </div>
        <div class="flex gap-2">
          <AppButton @click="showEditForm = true" class="bg-gray-600 text-white text-sm">Editar</AppButton>
        </div>
      </div>
    </div>

    <LoadingState v-if="loading" message="Carregando empresa..." />

    <template v-else-if="company">
      <!-- Summary Cards -->
      <div class="grid grid-cols-2 md:grid-cols-5 gap-4 mb-8">
        <StudentMetricCard icon="👥" :value="stats.total_employees" label="Funcionários" tone="blue" />
        <StudentMetricCard icon="📚" :value="stats.enrolled_employees" label="Matriculados" tone="green" />
        <StudentMetricCard icon="🎯" :value="stats.active_enrollments" label="Cursos Ativos" tone="orange" />
        <StudentMetricCard icon="✅" :value="stats.completed_enrollments" label="Concluídos" tone="purple" />
        <StudentMetricCard icon="🎓" :value="stats.certificates_issued" label="Certificados" tone="indigo" />
      </div>

      <!-- Actions -->
      <div class="flex flex-wrap gap-2 mb-6">
        <AppButton @click="showAddEmployee = true" class="bg-primary-600 text-white text-sm" data-testid="add-employee">
          + Adicionar Funcionário
        </AppButton>
        <AppButton @click="showImportModal = true" class="bg-secondary-600 text-white text-sm" data-testid="import-employees">
          Importar Funcionários
        </AppButton>
        <AppButton @click="showEnrollModal = true" class="bg-accent text-white text-sm" data-testid="enroll-employees">
          Matricular Funcionários
        </AppButton>
      </div>

      <!-- Employees Section -->
      <AppCard class="mb-8">
        <template #header>
          <h2 class="text-lg font-semibold text-secondary-900">Funcionários ({{ employees.length }})</h2>
        </template>

        <EmptyState
          v-if="employees.length === 0"
          title="Nenhum funcionário cadastrado"
          description="Adicione funcionários individualmente ou importe via CSV."
        />

        <div v-else class="overflow-x-auto">
          <table class="w-full border-collapse">
            <thead>
              <tr class="bg-gray-100">
                <th class="px-3 py-2 text-left text-sm font-semibold text-gray-700">Nome</th>
                <th class="px-3 py-2 text-left text-sm font-semibold text-gray-700">CPF</th>
                <th class="px-3 py-2 text-left text-sm font-semibold text-gray-700">E-mail</th>
                <th class="px-3 py-2 text-left text-sm font-semibold text-gray-700">Telefone</th>
                <th class="px-3 py-2 text-left text-sm font-semibold text-gray-700">Status</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="emp in employees" :key="emp.id" class="border-b hover:bg-gray-50 cursor-pointer" @click="$router.push(`/students/${emp.id}`)">
                <td class="px-3 py-2 text-sm font-medium">{{ emp.full_name || '-' }}</td>
                <td class="px-3 py-2 text-sm text-gray-600">{{ emp.cpf }}</td>
                <td class="px-3 py-2 text-sm text-gray-600">{{ emp.email || '-' }}</td>
                <td class="px-3 py-2 text-sm text-gray-600">{{ emp.phone || '-' }}</td>
                <td class="px-3 py-2">
                  <StatusBadge :status="emp.user_active === false ? 'inactive' : 'active'" />
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </AppCard>

      <!-- Enrollments Section -->
      <AppCard>
        <template #header>
          <h2 class="text-lg font-semibold text-secondary-900">Treinamentos / Matrículas</h2>
        </template>

        <EmptyState
          v-if="companyEnrollments.length === 0"
          title="Nenhum treinamento atribuído"
          description="Use 'Matricular Funcionários' para atribuir cursos aos funcionários desta empresa."
        />

        <div v-else class="overflow-x-auto">
          <table class="w-full border-collapse">
            <thead>
              <tr class="bg-gray-100">
                <th class="px-3 py-2 text-left text-sm font-semibold text-gray-700">Funcionário</th>
                <th class="px-3 py-2 text-left text-sm font-semibold text-gray-700">Curso</th>
                <th class="px-3 py-2 text-left text-sm font-semibold text-gray-700">Turma</th>
                <th class="px-3 py-2 text-left text-sm font-semibold text-gray-700">Status</th>
                <th class="px-3 py-2 text-left text-sm font-semibold text-gray-700">Origem</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="enr in companyEnrollments" :key="enr.id" class="border-b hover:bg-gray-50">
                <td class="px-3 py-2 text-sm">{{ getStudentName(enr.student_id) }}</td>
                <td class="px-3 py-2 text-sm">{{ getCourseName(enr.class_id) }}</td>
                <td class="px-3 py-2 text-sm text-gray-600">{{ getClassLabel(enr.class_id) }}</td>
                <td class="px-3 py-2"><StatusBadge :status="enr.status" /></td>
                <td class="px-3 py-2">
                  <span :class="enr.source === 'CORPORATE' ? 'bg-blue-100 text-blue-800' : 'bg-gray-100 text-gray-700'" class="px-2 py-0.5 rounded text-xs font-medium">
                    {{ enr.source === 'CORPORATE' ? 'Corporativo' : 'Individual' }}
                  </span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </AppCard>
    </template>

    <EmptyState v-else title="Empresa não encontrada" description="A empresa solicitada não existe ou foi removida." />

    <!-- Edit Modal -->
    <AppModal v-if="showEditForm" @close="showEditForm = false" title="Editar Empresa" size="lg">
      <form @submit.prevent="saveEdit" class="space-y-4">
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <AppInput v-model="editForm.legal_name" label="Razão Social *" required />
          <AppInput v-model="editForm.trade_name" label="Nome Fantasia" />
          <AppInput v-model="editForm.cnpj" label="CNPJ *" required />
          <AppInput v-model="editForm.rh_name" label="Contato (RH)" />
          <AppInput v-model="editForm.rh_email" label="E-mail do RH" type="email" />
          <AppInput v-model="editForm.rh_phone" label="Telefone do RH" />
          <AppInput v-model="editForm.city" label="Cidade" />
          <AppInput v-model="editForm.state" label="Estado" />
        </div>
        <AppInput v-model="editForm.address" label="Endereço" />
        <AppInput v-model="editForm.zip_code" label="CEP" />
        <div class="flex gap-2">
          <AppButton type="submit" class="bg-primary-600 text-white" :disabled="saving">Salvar</AppButton>
          <AppButton type="button" @click="showEditForm = false" class="bg-gray-300 text-gray-700">Cancelar</AppButton>
        </div>
      </form>
    </AppModal>

    <!-- Add Employee Modal -->
    <AppModal v-if="showAddEmployee" @close="showAddEmployee = false" title="Adicionar Funcionário" size="md">
      <form @submit.prevent="addEmployee" class="space-y-4">
        <AppInput v-model="employeeForm.full_name" label="Nome Completo *" required />
        <AppInput v-model="employeeForm.cpf" label="CPF *" placeholder="000.000.000-00" required />
        <AppInput v-model="employeeForm.email" label="E-mail *" type="email" required />
        <AppInput v-model="employeeForm.phone" label="Telefone" placeholder="(11) 99999-9999" />
        <div class="bg-blue-50 border border-blue-200 rounded-md p-3 text-sm text-blue-800">
          O funcionário receberá um link de ativação para definir sua própria senha. Nenhuma senha temporária é necessária.
        </div>
        <div v-if="activationLink" class="bg-green-50 border border-green-200 rounded-md p-3">
          <p class="text-sm font-medium text-green-900 mb-1">Funcionário cadastrado! Link de ativação:</p>
          <div class="flex items-center gap-2">
            <input :value="activationLink" readonly class="flex-1 text-xs bg-white border border-green-300 rounded px-2 py-1" />
            <AppButton type="button" @click="copyActivationLink" class="bg-green-600 text-white text-xs px-2 py-1">Copiar</AppButton>
          </div>
        </div>
        <div class="flex gap-2">
          <AppButton type="submit" class="bg-primary-600 text-white" :disabled="saving">Adicionar</AppButton>
          <AppButton type="button" @click="closeAddEmployee" class="bg-gray-300 text-gray-700">Fechar</AppButton>
        </div>
      </form>
    </AppModal>

    <!-- Import CSV Modal -->
    <AppModal v-if="showImportModal" @close="showImportModal = false" title="Importar Funcionários (CSV)" size="lg">
      <div class="space-y-4">
        <div class="bg-gray-50 border border-gray-200 rounded-md p-4">
          <p class="text-sm font-medium text-gray-700 mb-2">Formato esperado (CSV):</p>
          <code class="text-xs text-gray-600 block">full_name,cpf,email,phone</code>
          <button @click="downloadTemplate" class="text-sm text-primary-600 hover:underline mt-2">Baixar modelo CSV</button>
        </div>
        <div>
          <input type="file" accept=".csv" @change="onFileSelect" ref="fileInput" class="block w-full text-sm text-gray-500" />
        </div>

        <!-- Import Results -->
        <div v-if="importResult" class="space-y-3">
          <div class="grid grid-cols-4 gap-2 text-center">
            <div class="bg-green-50 rounded p-2">
              <div class="text-lg font-bold text-green-700">{{ importResult.created }}</div>
              <div class="text-xs text-green-600">Criados</div>
            </div>
            <div class="bg-yellow-50 rounded p-2">
              <div class="text-lg font-bold text-yellow-700">{{ importResult.existing }}</div>
              <div class="text-xs text-yellow-600">Existentes</div>
            </div>
            <div class="bg-orange-50 rounded p-2">
              <div class="text-lg font-bold text-orange-700">{{ importResult.invalid }}</div>
              <div class="text-xs text-orange-600">Inválidos</div>
            </div>
            <div class="bg-red-50 rounded p-2">
              <div class="text-lg font-bold text-red-700">{{ importResult.failed }}</div>
              <div class="text-xs text-red-600">Falhas</div>
            </div>
          </div>

          <div v-if="importResult.activation_tokens && importResult.activation_tokens.length > 0" class="bg-green-50 border border-green-200 rounded-md p-3">
            <p class="text-sm font-medium text-green-900 mb-2">Links de Ativação ({{ importResult.activation_tokens.length }}):</p>
            <div class="max-h-40 overflow-y-auto space-y-1">
              <div v-for="t in importResult.activation_tokens" :key="t.student_id" class="flex items-center gap-2 text-xs">
                <span class="flex-1 truncate">{{ t.full_name }}</span>
                <button @click="copyText(buildActivationLink(t.token))" class="text-green-700 hover:underline">Copiar link</button>
              </div>
            </div>
          </div>

          <div v-if="importResult.results && importResult.results.length > 0" class="max-h-60 overflow-y-auto">
            <table class="w-full text-xs">
              <thead>
                <tr class="bg-gray-100">
                  <th class="px-2 py-1 text-left">Linha</th>
                  <th class="px-2 py-1 text-left">Nome</th>
                  <th class="px-2 py-1 text-left">Status</th>
                  <th class="px-2 py-1 text-left">Erro</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="r in importResult.results" :key="r.row" class="border-b">
                  <td class="px-2 py-1">{{ r.row }}</td>
                  <td class="px-2 py-1">{{ r.full_name }}</td>
                  <td class="px-2 py-1">
                    <span :class="{
                      'text-green-700': r.status === 'created',
                      'text-yellow-700': r.status === 'existing',
                      'text-orange-700': r.status === 'invalid',
                      'text-red-700': r.status === 'failed',
                    }">{{ r.status }}</span>
                  </td>
                  <td class="px-2 py-1 text-gray-500">{{ r.error || '' }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <div class="flex gap-2">
          <AppButton @click="uploadCsv" class="bg-primary-600 text-white" :disabled="!selectedFile || importing">
            {{ importing ? 'Importando...' : 'Confirmar Importação' }}
          </AppButton>
          <AppButton @click="showImportModal = false" class="bg-gray-300 text-gray-700">Cancelar</AppButton>
        </div>
      </div>
    </AppModal>

    <!-- Bulk Enrollment Modal -->
    <AppModal v-if="showEnrollModal" @close="showEnrollModal = false" title="Matricular Funcionários" size="lg">
      <div class="space-y-4">
        <!-- Step 1: Select Course -->
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">Curso *</label>
          <select v-model="enrollForm.course_id" @change="onCourseChange" class="w-full px-3 py-2 border border-gray-300 rounded-md">
            <option value="">Selecione um curso</option>
            <option v-for="c in availableCourses" :key="c.id" :value="c.id">{{ c.name }}</option>
          </select>
        </div>

        <!-- Step 2: Select Class -->
        <div v-if="enrollForm.course_id">
          <label class="block text-sm font-medium text-gray-700 mb-1">Turma *</label>
          <select v-model="enrollForm.class_id" class="w-full px-3 py-2 border border-gray-300 rounded-md">
            <option value="">Selecione uma turma</option>
            <option v-for="cls in availableClassesForEnrollment" :key="cls.id" :value="cls.id">
              {{ new Date(cls.start_date).toLocaleDateString('pt-BR') }} a {{ new Date(cls.end_date).toLocaleDateString('pt-BR') }} ({{ getAvailableSeats(cls) }} vagas)
            </option>
          </select>
        </div>

        <!-- Step 3: Select Employees -->
        <div v-if="enrollForm.class_id">
          <div class="flex items-center justify-between mb-2">
            <label class="text-sm font-medium text-gray-700">Funcionários *</label>
            <button @click="selectAllEmployees" class="text-sm text-primary-600 hover:underline">Selecionar todos</button>
          </div>
          <input v-model="employeeSearch" type="text" placeholder="Buscar funcionário..." class="w-full px-3 py-2 border border-gray-300 rounded-md mb-2 text-sm" />
          <div class="max-h-48 overflow-y-auto border border-gray-200 rounded-md">
            <label v-for="emp in filteredEmployees" :key="emp.id" class="flex items-center px-3 py-2 hover:bg-gray-50 cursor-pointer">
              <input type="checkbox" :value="emp.id" v-model="enrollForm.student_ids" class="mr-2" />
              <span class="text-sm">{{ emp.full_name }} — {{ emp.cpf }}</span>
            </label>
          </div>
          <p class="text-sm text-gray-600 mt-1">{{ enrollForm.student_ids.length }} selecionados</p>
        </div>

        <!-- Confirmation Summary -->
        <div v-if="enrollForm.student_ids.length > 0" class="bg-gray-50 border border-gray-200 rounded-md p-3 text-sm">
          <div class="grid grid-cols-2 gap-2">
            <div><span class="text-gray-600">Empresa:</span> {{ company.trade_name || company.legal_name }}</div>
            <div><span class="text-gray-600">Curso:</span> {{ getCourseNameById(enrollForm.course_id) }}</div>
            <div><span class="text-gray-600">Quantidade:</span> {{ enrollForm.student_ids.length }}</div>
            <div><span class="text-gray-600">Vagas disponíveis:</span> {{ selectedClassSeats }}</div>
          </div>
          <div v-if="enrollForm.student_ids.length > selectedClassSeats" class="mt-2 text-red-600 font-medium">
            ⚠ Vagas insuficientes! Selecionados: {{ enrollForm.student_ids.length }}, Disponíveis: {{ selectedClassSeats }}
          </div>
        </div>

        <div class="flex gap-2">
          <AppButton
            @click="doBulkEnroll"
            class="bg-accent text-white"
            :disabled="!canEnroll || enrolling"
          >
            {{ enrolling ? 'Matriculando...' : `Matricular ${enrollForm.student_ids.length} funcionários` }}
          </AppButton>
          <AppButton @click="showEnrollModal = false" class="bg-gray-300 text-gray-700">Cancelar</AppButton>
        </div>
      </div>
    </AppModal>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { useRoute } from 'vue-router'
import api from '../api/client'
import AppCard from '../components/AppCard.vue'
import AppButton from '../components/AppButton.vue'
import AppInput from '../components/AppInput.vue'
import AppModal from '../components/AppModal.vue'
import EmptyState from '../components/EmptyState.vue'
import LoadingState from '../components/LoadingState.vue'
import StudentMetricCard from '../components/StudentMetricCard.vue'
import StatusBadge from '../components/StatusBadge.vue'
import { useToast } from '../composables/useToast'

const { success: toastSuccess, error: toastError } = useToast()
const route = useRoute()
const companyId = route.params.id

const company = ref(null)
const employees = ref([])
const companyEnrollments = ref([])
const allEnrollments = ref([])
const classes = ref([])
const courses = ref([])
const stats = ref({ total_employees: 0, enrolled_employees: 0, active_enrollments: 0, completed_enrollments: 0, certificates_issued: 0 })
const loading = ref(true)
const saving = ref(false)

// Modals
const showEditForm = ref(false)
const showAddEmployee = ref(false)
const showImportModal = ref(false)
const showEnrollModal = ref(false)

// Forms
const editForm = ref({})
const employeeForm = ref({ full_name: '', cpf: '', email: '', phone: '' })
const activationLink = ref('')
const enrollForm = ref({ course_id: '', class_id: '', student_ids: [] })
const employeeSearch = ref('')

// Import
const selectedFile = ref(null)
const importing = ref(false)
const importResult = ref(null)
const fileInput = ref(null)

// Enrollment
const enrolling = ref(false)

const availableCourses = computed(() => courses.value.filter(c => c.is_active))

const availableClassesForEnrollment = computed(() => {
  if (!enrollForm.value.course_id) return []
  return classes.value.filter(c => c.course_id === enrollForm.value.course_id && c.status === 'ABERTA')
})

const filteredEmployees = computed(() => {
  if (!employeeSearch.value) return employees.value
  const q = employeeSearch.value.toLowerCase()
  return employees.value.filter(e =>
    (e.full_name || '').toLowerCase().includes(q) || (e.cpf || '').includes(q)
  )
})

const selectedClassSeats = computed(() => {
  if (!enrollForm.value.class_id) return 0
  const cls = classes.value.find(c => c.id === enrollForm.value.class_id)
  return cls ? getAvailableSeats(cls) : 0
})

const canEnroll = computed(() =>
  enrollForm.value.class_id &&
  enrollForm.value.student_ids.length > 0 &&
  enrollForm.value.student_ids.length <= selectedClassSeats.value
)

const formatCnpj = (cnpj) => {
  if (!cnpj || cnpj.length !== 14) return cnpj
  return cnpj.replace(/(\d{2})(\d{3})(\d{3})(\d{4})(\d{2})/, '$1.$2.$3/$4-$5')
}

const getStudentName = (studentId) => {
  const emp = employees.value.find(e => e.id === studentId)
  return emp ? emp.full_name : '—'
}

const getCourseName = (classId) => {
  const cls = classes.value.find(c => c.id === classId)
  if (!cls) return '—'
  const course = courses.value.find(c => c.id === cls.course_id)
  return course ? course.name : '—'
}

const getCourseNameById = (courseId) => {
  return courses.value.find(c => c.id === courseId)?.name || '—'
}

const getClassLabel = (classId) => {
  const cls = classes.value.find(c => c.id === classId)
  if (!cls) return '—'
  return `${new Date(cls.start_date).toLocaleDateString('pt-BR')}`
}

const getAvailableSeats = (cls) => {
  const enrolled = allEnrollments.value.filter(
    e => e.class_id === cls.id && e.status !== 'CANCELADA'
  ).length
  return cls.max_students - enrolled
}

const loadData = async () => {
  loading.value = true
  try {
    const [companyRes, empRes, statsRes, classesRes, coursesRes, enrollmentsRes] = await Promise.all([
      api.get(`/api/v1/companies/${companyId}`),
      api.get(`/api/v1/companies/${companyId}/employees`),
      api.get(`/api/v1/companies/${companyId}/stats`),
      api.get('/api/v1/classes/'),
      api.get('/api/v1/courses/'),
      api.get('/api/v1/enrollments/'),
    ])
    company.value = companyRes.data
    employees.value = empRes.data
    stats.value = statsRes.data
    classes.value = classesRes.data
    courses.value = coursesRes.data
    allEnrollments.value = enrollmentsRes.data

    // Filter enrollments for this company's employees
    const empIds = new Set(employees.value.map(e => e.id))
    companyEnrollments.value = allEnrollments.value.filter(e => empIds.has(e.student_id))
  } catch (error) {
    toastError('Erro ao carregar dados da empresa')
  } finally {
    loading.value = false
  }
}

const saveEdit = async () => {
  saving.value = true
  try {
    await api.put(`/api/v1/companies/${companyId}`, editForm.value)
    company.value = { ...company.value, ...editForm.value }
    showEditForm.value = false
    toastSuccess('Empresa atualizada com sucesso!')
  } catch (error) {
    toastError('Erro ao atualizar empresa')
  } finally {
    saving.value = false
  }
}

const addEmployee = async () => {
  saving.value = true
  activationLink.value = ''
  try {
    const res = await api.post(`/api/v1/companies/${companyId}/employees`, employeeForm.value)
    if (res.data.activation_token) {
      activationLink.value = buildActivationLink(res.data.activation_token)
    }
    toastSuccess('Funcionário cadastrado com sucesso!')
    employeeForm.value = { full_name: '', cpf: '', email: '', phone: '' }
    await loadData()
  } catch (error) {
    const detail = error.response?.data?.detail
    toastError('Erro ao cadastrar funcionário: ' + (detail || error.message))
  } finally {
    saving.value = false
  }
}

const closeAddEmployee = () => {
  showAddEmployee.value = false
  activationLink.value = ''
  employeeForm.value = { full_name: '', cpf: '', email: '', phone: '' }
}

const buildActivationLink = (token) => {
  const base = window.location.origin
  return `${base}/redefinir-senha?token=${token}&activation=1`
}

const copyActivationLink = () => {
  copyText(activationLink.value)
  toastSuccess('Link copiado!')
}

const copyText = (text) => {
  navigator.clipboard.writeText(text)
  toastSuccess('Copiado para a área de transferência!')
}

const downloadTemplate = () => {
  const csv = 'full_name,cpf,email,phone\nJoão Silva,12345678901,joao@empresa.com,11999999999\n'
  const blob = new Blob([csv], { type: 'text/csv' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = 'modelo_funcionarios.csv'
  a.click()
  URL.revokeObjectURL(url)
}

const onFileSelect = (e) => {
  selectedFile.value = e.target.files[0]
}

const uploadCsv = async () => {
  if (!selectedFile.value) return
  importing.value = true
  importResult.value = null
  try {
    const formData = new FormData()
    formData.append('file', selectedFile.value)
    const res = await api.post(`/api/v1/companies/${companyId}/employees/import`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    importResult.value = res.data
    toastSuccess(`${res.data.created} funcionários importados!`)
    await loadData()
  } catch (error) {
    const detail = error.response?.data?.detail
    toastError('Erro na importação: ' + (detail || error.message))
  } finally {
    importing.value = false
  }
}

const onCourseChange = () => {
  enrollForm.value.class_id = ''
  enrollForm.value.student_ids = []
}

const selectAllEmployees = () => {
  enrollForm.value.student_ids = filteredEmployees.value.map(e => e.id)
}

const doBulkEnroll = async () => {
  if (!canEnroll.value) return
  enrolling.value = true
  try {
    const payload = {
      class_id: enrollForm.value.class_id,
      student_ids: enrollForm.value.student_ids,
      company_id: companyId,
      source: 'CORPORATE',
      status: 'CONFIRMADA',
      price_per_student: 0,
      create_payment: false,
    }
    const res = await api.post('/api/v1/enrollments/bulk', payload)
    toastSuccess(`${res.data.enrollment_ids.length} funcionários matriculados!`)
    showEnrollModal.value = false
    enrollForm.value = { course_id: '', class_id: '', student_ids: [] }
    await loadData()
  } catch (error) {
    const detail = error.response?.data?.detail
    toastError('Erro ao matricular: ' + (detail || error.message))
  } finally {
    enrolling.value = false
  }
}

onMounted(() => {
  editForm.value = {}
  loadData()
})

// Watch for edit form opening
import { watch } from 'vue'
watch(showEditForm, (val) => {
  if (val && company.value) {
    editForm.value = { ...company.value }
  }
})
</script>
