<template>
  <div>
    <AppPageHeader title="Turmas" description="Gerencie as turmas disponíveis.">
      <template #actions>
        <AppButton
          v-if="isAdmin"
          @click="showForm = true"
          class="bg-primary-600 text-white"
          data-testid="new-class-btn"
        >
          + Nova Turma
        </AppButton>
      </template>
    </AppPageHeader>

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
                :disabled="!!editingId"
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
            <AppButton type="submit" class="bg-primary-600 text-white" :disabled="saving" data-testid="save-class-btn">
              {{ saving ? 'Salvando...' : 'Salvar' }}
            </AppButton>
            <AppButton type="button" @click="cancelForm" class="bg-gray-300 text-gray-700" data-testid="cancel-class-btn">
              Cancelar
            </AppButton>
          </div>
        </form>
      </AppCard>

      <!-- Loading -->
      <LoadingState v-if="loading" message="Carregando turmas..." />

      <!-- Error -->
      <AppAlert v-else-if="loadError" type="error" closable @close="loadError = ''">
        {{ loadError }}
        <button @click="loadClasses" class="underline ml-2">Tentar novamente</button>
      </AppAlert>

      <!-- Empty -->
      <EmptyState
        v-else-if="classes.length === 0"
        title="Nenhuma turma disponível"
        description="Clique em 'Nova Turma' para criar a primeira turma."
      />

      <!-- Success -->
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
            <p v-if="cls.ead_link"><strong>Link EAD:</strong> <a :href="cls.ead_link" target="_blank" rel="noopener noreferrer" class="text-primary-600 hover:underline">Acessar</a></p>
            <p v-if="cls.description" class="text-gray-600 mt-3">{{ cls.description }}</p>
          </div>
          <div v-if="isAdmin" class="mt-4 flex gap-2">
            <AppButton @click="editClass(cls)" class="bg-blue-600 text-white text-sm flex-1" data-testid="edit-class-btn">Editar</AppButton>
            <AppButton @click="confirmDelete(cls)" class="bg-red-600 text-white text-sm flex-1" data-testid="delete-class-btn">Excluir</AppButton>
          </div>
        </AppCard>
      </div>

    <!-- Delete confirmation -->
    <ConfirmDialog
      v-model="showDeleteConfirm"
      title="Excluir turma"
      :message="deleteMessage"
      confirm-text="Excluir"
      cancel-text="Cancelar"
      danger
      :loading="deleting"
      @confirm="doDelete"
      data-testid="delete-class-dialog"
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
const { success: toastSuccess, error: toastError } = useToast()

const classes = ref([])
const courses = ref([])
const loading = ref(false)
const saving = ref(false)
const loadError = ref('')
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

// Delete state
const showDeleteConfirm = ref(false)
const deleting = ref(false)
const pendingDeleteId = ref(null)
const pendingDeleteName = ref('')

const isAdmin = computed(() => authStore.userRole?.toLowerCase() === 'admin' || authStore.userRole?.toLowerCase() === 'super_admin')

const deleteMessage = computed(() =>
  `Excluir a turma de "${pendingDeleteName.value}"? Esta ação não pode ser desfeita.`
)

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
    // silent — courses list is for display
  }
}

const loadClasses = async () => {
  loading.value = true
  loadError.value = ''
  try {
    const response = await api.get('/api/v1/classes/')
    classes.value = response.data
  } catch (error) {
    loadError.value = 'Não foi possível carregar as turmas. Tente novamente.'
  } finally {
    loading.value = false
  }
}

const saveClass = async () => {
  saving.value = true
  try {
    const payload = {
      ...form.value,
      responsible_admin_id: authStore.user?.id,
      max_students: Number(form.value.max_students),
      location: form.value.location || null,
      ead_link: form.value.ead_link || null,
      description: form.value.description || null,
    }

    if (editingId.value) {
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
      toastSuccess('Turma atualizada com sucesso!')
    } else {
      await api.post('/api/v1/classes/', payload)
      toastSuccess('Turma criada com sucesso!')
    }
    resetForm()
    loadClasses()
  } catch (error) {
    const detail = error.response?.data?.detail
    const message = typeof detail === 'object' ? JSON.stringify(detail) : (detail || error.message)
    toastError('Erro ao salvar turma: ' + message)
  } finally {
    saving.value = false
  }
}

const editClass = (cls) => {
  editingId.value = cls.id
  form.value = { ...cls }
  showForm.value = true
}

const confirmDelete = (cls) => {
  pendingDeleteId.value = cls.id
  pendingDeleteName.value = getCourseNameById(cls.course_id)
  showDeleteConfirm.value = true
}

const doDelete = async () => {
  deleting.value = true
  try {
    await api.delete(`/api/v1/classes/${pendingDeleteId.value}`)
    toastSuccess('Turma excluída com sucesso!')
    showDeleteConfirm.value = false
    loadClasses()
  } catch (error) {
    toastError('Erro ao excluir turma: ' + (error.response?.data?.detail || ''))
  } finally {
    deleting.value = false
  }
}

const cancelForm = () => {
  resetForm()
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
