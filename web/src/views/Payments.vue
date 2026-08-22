<template>
  <div>
    <AppPageHeader title="Pagamentos" description="Gerencie os pagamentos e simulações.">
      <template #actions>
        <AppButton
          v-if="isAdmin"
          @click="showForm = true"
          class="bg-primary-600 text-white"
          data-testid="new-payment-btn"
        >
          + Novo Pagamento
        </AppButton>
      </template>
    </AppPageHeader>

      <!-- Formulário -->
      <AppCard v-if="showForm" class="mb-8">
        <template #header>
          <h2 class="text-xl font-semibold text-secondary-900">{{ editingId ? 'Editar' : 'Novo' }} Pagamento</h2>
        </template>
        <form @submit.prevent="savePayment" class="space-y-4">
          <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">Matrícula *</label>
              <select
                v-model="form.enrollment_id"
                class="w-full px-4 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500"
                required
              >
                <option value="">Selecione uma matrícula</option>
                <option v-for="enrollment in enrollments" :key="enrollment.id" :value="enrollment.id">
                  {{ getStudentCpfById(enrollment.student_id) }} - {{ getClassNameById(enrollment.class_id) }}
                </option>
              </select>
            </div>
            <AppInput
              v-model.number="form.amount"
              label="Valor"
              type="number"
              step="0.01"
              required
            />
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">Método</label>
              <select
                v-model="form.method"
                class="w-full px-4 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500"
                required
              >
                <option value="CARTAO">Cartão</option>
                <option value="BOLETO">Boleto</option>
                <option value="PIX">PIX</option>
              </select>
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">Status</label>
              <select
                v-model="form.status"
                class="w-full px-4 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500"
              >
                <option value="PENDENTE">Pendente</option>
                <option value="PROCESSANDO">Processando</option>
                <option value="APROVADO">Aprovado</option>
                <option value="RECUSADO">Recusado</option>
                <option value="REEMBOLSADO">Reembolsado</option>
              </select>
            </div>
            <AppInput
              v-model="form.installments"
              label="Parcelas"
              placeholder="1x"
            />
          </div>
          <div class="flex gap-2">
            <AppButton type="submit" class="bg-primary-600 text-white" :disabled="saving" data-testid="save-payment-btn">Salvar</AppButton>
            <AppButton type="button" @click="showForm = false" class="bg-gray-300 text-gray-700" data-testid="cancel-payment-btn">Cancelar</AppButton>
          </div>
        </form>
      </AppCard>

      <!-- Erro de carregamento -->
      <AppAlert
        v-if="loadError"
        type="error"
        closable
        class="mb-6"
        @close="loadError = ''"
      >
        {{ loadError }}
      </AppAlert>

      <!-- Lista -->
      <LoadingState v-if="loading" message="Carregando pagamentos..." />

      <EmptyState
        v-else-if="payments.length === 0"
        title="Nenhum pagamento registrado"
        description="Clique em 'Novo Pagamento' para registrar o primeiro pagamento."
      />

      <div v-else class="overflow-x-auto">
        <table class="w-full border-collapse">
          <thead>
            <tr class="bg-gray-200">
              <th class="px-4 py-2 text-left font-semibold text-gray-700">Matrícula</th>
              <th class="px-4 py-2 text-left font-semibold text-gray-700">Valor</th>
              <th class="px-4 py-2 text-left font-semibold text-gray-700">Método</th>
              <th class="px-4 py-2 text-left font-semibold text-gray-700">Provider</th>
              <th class="px-4 py-2 text-left font-semibold text-gray-700">Status</th>
              <th class="px-4 py-2 text-left font-semibold text-gray-700">Data</th>
              <th class="px-4 py-2 text-left font-semibold text-gray-700">Pago em</th>
              <th class="px-4 py-2 text-left font-semibold text-gray-700">Ações</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="payment in payments" :key="payment.id" class="border-b hover:bg-gray-50">
              <td class="px-4 py-2">{{ getStudentCpfByPayment(payment) }}</td>
              <td class="px-4 py-2">R$ {{ formatPrice(payment.amount) }}</td>
              <td class="px-4 py-2">{{ formatMethod(payment.method) }}</td>
              <td class="px-4 py-2 text-xs">{{ formatProvider(payment.provider) }}</td>
              <td class="px-4 py-2">
                <span :class="['px-2 py-1 rounded text-xs font-semibold', getStatusColor(payment.status)]">
                  {{ formatStatus(payment.status) }}
                </span>
              </td>
              <td class="px-4 py-2">{{ formatDate(payment.created_at) }}</td>
              <td class="px-4 py-2 text-xs">{{ payment.paid_at ? formatDate(payment.paid_at) : '—' }}</td>
              <td class="px-4 py-2 space-x-2">
                <AppButton @click="editPayment(payment)" class="bg-blue-600 text-white text-xs px-2 py-1" data-testid="edit-payment-btn">Editar</AppButton>
                <AppButton @click="confirmDelete(payment)" class="bg-red-600 text-white text-xs px-2 py-1" data-testid="delete-payment-btn">Deletar</AppButton>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

    <ConfirmDialog
      v-model="showDeleteConfirm"
      title="Excluir pagamento"
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
import { useToast } from '../composables/useToast'
import api from '../api/client'
import AppPageHeader from '../components/AppPageHeader.vue'
import AppCard from '../components/AppCard.vue'
import AppButton from '../components/AppButton.vue'
import AppInput from '../components/AppInput.vue'
import AppAlert from '../components/AppAlert.vue'
import EmptyState from '../components/EmptyState.vue'
import LoadingState from '../components/LoadingState.vue'
import ConfirmDialog from '../components/ConfirmDialog.vue'

const authStore = useAuthStore()
const { error: toastError } = useToast()

const payments = ref([])
const enrollments = ref([])
const students = ref([])
const classes = ref([])
const courses = ref([])
const loading = ref(false)
const showForm = ref(false)
const editingId = ref(null)
const form = ref({
  enrollment_id: '',
  amount: 0,
  method: 'CARTAO',
  status: 'PENDENTE',
  installments: '',
})

const showDeleteConfirm = ref(false)
const deleting = ref(false)
const pendingDeleteId = ref(null)
const pendingDeleteName = ref('')
const saving = ref(false)
const loadError = ref('')

const isAdmin = computed(() => authStore.userRole?.toLowerCase() === 'admin' || authStore.userRole?.toLowerCase() === 'super_admin')

const deleteMessage = computed(() =>
  `Excluir o pagamento de "${pendingDeleteName.value}"? Esta ação não pode ser desfeita.`
)

const formatDate = (date) => {
  return new Date(date).toLocaleDateString('pt-BR')
}

const formatPrice = (price) => {
  return parseFloat(price).toFixed(2).replace('.', ',')
}

const formatMethod = (method) => {
  const map = {
    'CARTAO': 'Cartão',
    'BOLETO': 'Boleto',
    'PIX': 'PIX',
    'UNDEFINED': 'A definir',
  }
  return map[method] || method
}

const formatProvider = (provider) => {
  const map = {
    'MERCADO_PAGO': 'Mercado Pago',
    'ASAAS': 'Asaas',
  }
  return map[provider] || provider || '—'
}

const formatStatus = (status) => {
  const map = {
    'PENDENTE': 'Pendente',
    'PROCESSANDO': 'Processando',
    'APROVADO': 'Aprovado',
    'RECUSADO': 'Recusado',
    'REEMBOLSADO': 'Reembolsado'
  }
  return map[status] || status
}

const getStatusColor = (status) => {
  const colors = {
    'PENDENTE': 'bg-yellow-100 text-yellow-800',
    'PROCESSANDO': 'bg-blue-100 text-blue-800',
    'APROVADO': 'bg-green-100 text-green-800',
    'RECUSADO': 'bg-red-100 text-red-800',
    'REEMBOLSADO': 'bg-gray-100 text-gray-800'
  }
  return colors[status] || 'bg-gray-100 text-gray-800'
}

const getStudentCpfById = (id) => {
  return students.value.find(s => s.id === id)?.cpf || 'Aluno desconhecido'
}

const getCourseNameById = (id) => {
  return courses.value.find(c => c.id === id)?.name || 'Curso desconhecido'
}

const getClassNameById = (classId) => {
  const cls = classes.value.find(c => c.id === classId)
  if (!cls) return 'Turma desconhecida'
  return `${getCourseNameById(cls.course_id)} - ${formatDate(cls.start_date)}`
}

const getStudentCpfByPayment = (payment) => {
  const enrollment = enrollments.value.find(e => e.id === payment.enrollment_id)
  if (!enrollment) return 'Desconhecido'
  return getStudentCpfById(enrollment.student_id)
}

const loadPayments = async () => {
  loading.value = true
  loadError.value = ''
  try {
    const response = await api.get('/api/v1/payments/')
    payments.value = response.data
  } catch (error) {
    console.error('Erro ao carregar pagamentos:', error)
    loadError.value = 'Erro ao carregar pagamentos. Tente novamente.'
  } finally {
    loading.value = false
  }
}

const loadDependencies = async () => {
  try {
    const [enrollmentsRes, studentsRes, classesRes, coursesRes] = await Promise.all([
      api.get('/api/v1/enrollments/'),
      api.get('/api/v1/students/'),
      api.get('/api/v1/classes/'),
      api.get('/api/v1/courses/')
    ])
    enrollments.value = enrollmentsRes.data
    students.value = studentsRes.data
    classes.value = classesRes.data
    courses.value = coursesRes.data
  } catch (error) {
    console.error('Erro ao carregar dependências:', error)
  }
}

const savePayment = async () => {
  saving.value = true
  try {
    if (editingId.value) {
      await api.put(`/api/v1/payments/${editingId.value}`, { status: form.value.status })
    } else {
      await api.post('/api/v1/payments/', form.value)
    }
    resetForm()
    loadPayments()
  } catch (error) {
    console.error('Erro ao salvar pagamento:', error)
    toastError('Erro ao salvar pagamento: ' + (error.response?.data?.detail || error.message))
  } finally {
    saving.value = false
  }
}

const editPayment = (payment) => {
  editingId.value = payment.id
  form.value = {
    enrollment_id: payment.enrollment_id,
    amount: payment.amount,
    method: payment.method,
    status: payment.status,
    installments: payment.installments || '',
  }
  showForm.value = true
}

const confirmDelete = (payment) => {
  pendingDeleteId.value = payment.id
  pendingDeleteName.value = getStudentCpfByPayment(payment)
  showDeleteConfirm.value = true
}

const doDelete = async () => {
  deleting.value = true
  try {
    await api.delete(`/api/v1/payments/${pendingDeleteId.value}`)
    showDeleteConfirm.value = false
    pendingDeleteId.value = null
    pendingDeleteName.value = ''
    loadPayments()
  } catch (error) {
    console.error('Erro ao deletar pagamento:', error)
    toastError('Erro ao deletar pagamento')
  } finally {
    deleting.value = false
  }
}

const resetForm = () => {
  editingId.value = null
  form.value = {
    enrollment_id: '',
    amount: 0,
    method: 'CARTAO',
    status: 'PENDENTE',
    installments: '',
  }
  showForm.value = false
}

onMounted(() => {
  loadDependencies()
  loadPayments()
})
</script>
