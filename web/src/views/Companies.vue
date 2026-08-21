<template>
  <div>
    <AppPageHeader title="Empresas" description="Gerencie as empresas contratantes e seus funcionários.">
      <template #actions>
        <AppButton
          @click="showForm = true"
          class="bg-primary-600 text-white"
          data-testid="new-company"
        >
          + Nova Empresa
        </AppButton>
      </template>
    </AppPageHeader>

    <!-- Form -->
    <AppCard v-if="showForm" class="mb-8">
      <template #header>
        <h2 class="text-xl font-semibold text-secondary-900">{{ editingId ? 'Editar' : 'Nova' }} Empresa</h2>
      </template>
      <form @submit.prevent="saveCompany" class="space-y-4">
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <AppInput v-model="form.legal_name" label="Razão Social *" placeholder="Empresa ABC Ltda." required />
          <AppInput v-model="form.trade_name" label="Nome Fantasia" placeholder="Empresa ABC" />
          <AppInput v-model="form.cnpj" label="CNPJ *" placeholder="00.000.000/0000-00" required />
          <AppInput v-model="form.rh_name" label="Contato (RH)" placeholder="Nome do responsável" />
          <AppInput v-model="form.rh_email" label="E-mail do RH" type="email" placeholder="rh@empresa.com" />
          <AppInput v-model="form.rh_phone" label="Telefone do RH" placeholder="(11) 99999-9999" />
          <AppInput v-model="form.city" label="Cidade" placeholder="São Paulo" />
          <AppInput v-model="form.state" label="Estado" placeholder="SP" />
        </div>
        <AppInput v-model="form.address" label="Endereço" placeholder="Rua, número, complemento" />
        <AppInput v-model="form.zip_code" label="CEP" placeholder="00000-000" />
        <div class="flex gap-2">
          <AppButton type="submit" class="bg-primary-600 text-white" :disabled="saving" data-testid="save-company">Salvar</AppButton>
          <AppButton type="button" @click="cancelForm" class="bg-gray-300 text-gray-700" data-testid="cancel-company">Cancelar</AppButton>
        </div>
      </form>
    </AppCard>

    <!-- List -->
    <LoadingState v-if="loading" message="Carregando empresas..." />

    <AppAlert v-else-if="loadError" type="error" closable @close="loadError = ''">
      {{ loadError }}
    </AppAlert>

    <EmptyState
      v-else-if="companies.length === 0"
      title="Nenhuma empresa cadastrada"
      description="Clique em 'Nova Empresa' para cadastrar a primeira empresa contratante."
    />

    <div v-else class="overflow-x-auto">
      <table class="w-full border-collapse">
        <thead>
          <tr class="bg-gray-200">
            <th class="px-4 py-2 text-left font-semibold text-gray-700">Empresa</th>
            <th class="px-4 py-2 text-left font-semibold text-gray-700">CNPJ</th>
            <th class="px-4 py-2 text-left font-semibold text-gray-700">Contato RH</th>
            <th class="px-4 py-2 text-left font-semibold text-gray-700">Funcionários</th>
            <th class="px-4 py-2 text-left font-semibold text-gray-700">Matrículas</th>
            <th class="px-4 py-2 text-left font-semibold text-gray-700">Ações</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="company in companies" :key="company.id" class="border-b hover:bg-gray-50">
            <td class="px-4 py-2 font-medium">{{ company.trade_name || company.legal_name }}</td>
            <td class="px-4 py-2 text-sm text-gray-600">{{ formatCnpj(company.cnpj) }}</td>
            <td class="px-4 py-2 text-sm text-gray-600">
              <div v-if="company.rh_name">{{ company.rh_name }}</div>
              <div v-if="company.rh_email" class="text-xs text-gray-500">{{ company.rh_email }}</div>
            </td>
            <td class="px-4 py-2 text-center">{{ employeeCounts[company.id] || 0 }}</td>
            <td class="px-4 py-2 text-center">{{ enrollmentCounts[company.id] || 0 }}</td>
            <td class="px-4 py-2 space-x-2">
              <AppButton @click="$router.push(`/companies/${company.id}`)" class="bg-blue-600 text-white text-xs px-2 py-1" data-testid="view-company">Ver</AppButton>
              <AppButton @click="editCompany(company)" class="bg-gray-600 text-white text-xs px-2 py-1" data-testid="edit-company">Editar</AppButton>
              <AppButton @click="deleteCompany(company)" class="bg-red-600 text-white text-xs px-2 py-1" data-testid="delete-company">Excluir</AppButton>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <ConfirmDialog
      v-model="showDeleteConfirm"
      title="Excluir empresa"
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

const companies = ref([])
const students = ref([])
const enrollments = ref([])
const loading = ref(false)
const showForm = ref(false)
const editingId = ref(null)
const saving = ref(false)
const loadError = ref('')
const showDeleteConfirm = ref(false)
const deleting = ref(false)
const pendingDeleteId = ref(null)
const pendingDeleteName = ref('')

const form = ref({
  legal_name: '',
  trade_name: '',
  cnpj: '',
  rh_name: '',
  rh_email: '',
  rh_phone: '',
  address: '',
  city: '',
  state: '',
  zip_code: '',
})

const employeeCounts = computed(() => {
  const counts = {}
  for (const s of students.value) {
    if (s.company_id) counts[s.company_id] = (counts[s.company_id] || 0) + 1
  }
  return counts
})

const enrollmentCounts = computed(() => {
  const counts = {}
  const studentCompanyMap = {}
  for (const s of students.value) {
    if (s.company_id) studentCompanyMap[s.id] = s.company_id
  }
  for (const e of enrollments.value) {
    const cid = studentCompanyMap[e.student_id]
    if (cid) counts[cid] = (counts[cid] || 0) + 1
  }
  return counts
})

const deleteMessage = computed(() =>
  `Excluir a empresa "${pendingDeleteName.value}"? Esta ação não pode ser desfeita.`
)

const formatCnpj = (cnpj) => {
  if (!cnpj || cnpj.length !== 14) return cnpj
  return cnpj.replace(/(\d{2})(\d{3})(\d{3})(\d{4})(\d{2})/, '$1.$2.$3/$4-$5')
}

const loadCompanies = async () => {
  loading.value = true
  loadError.value = ''
  try {
    const response = await api.get('/api/v1/companies/')
    companies.value = response.data
  } catch (error) {
    loadError.value = 'Erro ao carregar empresas. Tente novamente.'
  } finally {
    loading.value = false
  }
}

const loadStudents = async () => {
  try {
    const response = await api.get('/api/v1/students/')
    students.value = response.data
  } catch (error) { /* silent */ }
}

const loadEnrollments = async () => {
  try {
    const response = await api.get('/api/v1/enrollments/')
    enrollments.value = response.data
  } catch (error) { /* silent */ }
}

const saveCompany = async () => {
  saving.value = true
  try {
    if (editingId.value) {
      await api.put(`/api/v1/companies/${editingId.value}`, form.value)
      toastSuccess('Empresa atualizada com sucesso!')
    } else {
      await api.post('/api/v1/companies/', form.value)
      toastSuccess('Empresa cadastrada com sucesso!')
    }
    resetForm()
    await loadCompanies()
  } catch (error) {
    const detail = error.response?.data?.detail
    toastError('Erro ao salvar empresa: ' + (detail || error.message))
  } finally {
    saving.value = false
  }
}

const editCompany = (company) => {
  editingId.value = company.id
  form.value = { ...company }
  showForm.value = true
}

const cancelForm = () => {
  resetForm()
}

const deleteCompany = (company) => {
  pendingDeleteId.value = company.id
  pendingDeleteName.value = company.trade_name || company.legal_name
  showDeleteConfirm.value = true
}

const doDelete = async () => {
  deleting.value = true
  try {
    await api.delete(`/api/v1/companies/${pendingDeleteId.value}`)
    await loadCompanies()
    showDeleteConfirm.value = false
    toastSuccess('Empresa excluída com sucesso!')
  } catch (error) {
    toastError('Erro ao excluir empresa')
  } finally {
    deleting.value = false
    pendingDeleteId.value = null
    pendingDeleteName.value = ''
  }
}

const resetForm = () => {
  editingId.value = null
  form.value = {
    legal_name: '',
    trade_name: '',
    cnpj: '',
    rh_name: '',
    rh_email: '',
    rh_phone: '',
    address: '',
    city: '',
    state: '',
    zip_code: '',
  }
  showForm.value = false
}

onMounted(async () => {
  await Promise.all([loadCompanies(), loadStudents(), loadEnrollments()])
})
</script>
