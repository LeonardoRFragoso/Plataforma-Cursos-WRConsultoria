<template>
  <div>
    <AppPageHeader title="Cursos" description="Gerencie o catálogo de cursos.">
      <template #actions>
        <AppButton
          v-if="isAdmin"
          @click="showForm = true"
          class="bg-primary-600 text-white"
          data-testid="new-course-btn"
        >
          + Novo Curso
        </AppButton>
      </template>
    </AppPageHeader>

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
          <!-- Course media fields -->
          <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
            <AppInput
              v-model="form.cover_image_url"
              label="URL da imagem de capa (opcional)"
              placeholder="/assets/wr/courses/nr-10.webp ou https://..."
              data-testid="course-cover-image-url"
            />
            <AppInput
              v-model="form.cover_image_alt"
              label="Texto alternativo da capa (opcional)"
              placeholder="Descrição da imagem para acessibilidade"
              data-testid="course-cover-image-alt"
            />
          </div>
          <!-- Cover preview -->
          <div v-if="form.cover_image_url" class="mt-2">
            <p class="text-sm text-gray-500 mb-1">Pré-visualização:</p>
            <img
              :src="form.cover_image_url"
              :alt="form.cover_image_alt || 'Preview'"
              class="w-full max-w-xs rounded-md border border-gray-200"
              style="aspect-ratio: 16/9; object-fit: cover;"
              data-testid="course-cover-preview"
            />
          </div>
          <div class="flex gap-2">
            <AppButton type="submit" class="bg-primary-600 text-white" :disabled="saving" data-testid="save-course-btn">
              {{ saving ? 'Salvando...' : 'Salvar' }}
            </AppButton>
            <AppButton
              type="button"
              @click="cancelForm"
              class="bg-gray-300 text-gray-700"
              data-testid="cancel-course-btn"
            >
              Cancelar
            </AppButton>
          </div>
        </form>
      </AppCard>

      <!-- Loading -->
      <LoadingState v-if="loading" message="Carregando cursos..." />

      <!-- Error -->
      <AppAlert v-else-if="loadError" type="error" closable @close="loadError = ''">
        {{ loadError }}
        <button @click="loadCourses" class="underline ml-2">Tentar novamente</button>
      </AppAlert>

      <!-- Empty -->
      <EmptyState
        v-else-if="courses.length === 0"
        title="Nenhum curso cadastrado"
        description="Clique em 'Novo Curso' para criar o primeiro curso."
      />

      <!-- Success list -->
      <div v-else class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        <AppCard v-for="course in courses" :key="course.id" class="hover:shadow-lg transition-shadow">
          <template #header>
            <div class="flex items-start gap-3">
              <CourseCover
                :course="course"
                ratio="16/9"
                fit="cover"
                loading="lazy"
                wrapper-class="w-24 shrink-0 rounded-md overflow-hidden"
                img-test-id="admin-course-thumb-img"
                fb-test-id="admin-course-thumb-fallback"
              />
              <h3 class="text-lg font-semibold text-secondary-900 flex-1">{{ course.name }}</h3>
            </div>
          </template>
          <div class="space-y-2 text-sm">
            <p><strong>Código:</strong> {{ course.code }}</p>
            <p><strong>Categoria:</strong> {{ course.category }}</p>
            <p><strong>Carga Horária:</strong> {{ course.carga_horaria }}h</p>
            <p><strong>Modalidade:</strong> {{ formatModality(course.modality) }}</p>
            <p><strong>Preço:</strong> R$ {{ formatPrice(course.price) }}</p>
            <p v-if="course.description" class="text-gray-600 mt-3">{{ course.description }}</p>
          </div>
          <div v-if="isAdmin" class="mt-4 flex gap-2 flex-wrap">
            <AppButton
              @click="manageLessons(course)"
              class="bg-teal-600 text-white text-sm flex-1"
              data-testid="manage-lessons-btn"
            >
              Gerenciar Aulas
            </AppButton>
            <AppButton
              @click="viewProgress(course)"
              class="bg-indigo-600 text-white text-sm flex-1"
              data-testid="view-progress-btn"
            >
              Acompanhar Alunos
            </AppButton>
            <AppButton
              @click="editCourse(course)"
              class="bg-blue-600 text-white text-sm flex-1"
              data-testid="edit-course-btn"
            >
              Editar
            </AppButton>
            <AppButton
              @click="confirmDelete(course)"
              class="bg-red-600 text-white text-sm flex-1"
              data-testid="delete-course-btn"
            >
              Excluir
            </AppButton>
          </div>
        </AppCard>
      </div>

    <!-- Delete confirmation -->
    <ConfirmDialog
      v-model="showDeleteConfirm"
      :title="'Excluir curso'"
      :message="deleteMessage"
      confirm-text="Excluir"
      cancel-text="Cancelar"
      danger
      :loading="deleting"
      @confirm="doDelete"
      data-testid="delete-course-dialog"
    />
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
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
import CourseCover from '../components/CourseCover.vue'

const authStore = useAuthStore()
const router = useRouter()
const { success: toastSuccess, error: toastError } = useToast()

const courses = ref([])
const loading = ref(false)
const saving = ref(false)
const showForm = ref(false)
const editingId = ref(null)
const loadError = ref('')

// Delete confirmation state
const showDeleteConfirm = ref(false)
const deleting = ref(false)
const pendingDeleteId = ref(null)
const pendingDeleteName = ref('')

const form = ref({
  code: '',
  name: '',
  category: '',
  carga_horaria: 0,
  price: 0,
  modality: 'PRESENCIAL',
  description: '',
  cover_image_url: '',
  cover_image_alt: '',
})

const isAdmin = computed(() => {
  const role = authStore.userRole?.toLowerCase()
  return role === 'admin' || role === 'super_admin'
})

const deleteMessage = computed(() =>
  `Excluir o curso "${pendingDeleteName.value}"? Esta ação não pode ser desfeita.`
)

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
  loadError.value = ''
  try {
    const response = await api.get('/api/v1/courses/')
    courses.value = response.data
  } catch (error) {
    loadError.value = 'Não foi possível carregar os cursos. Tente novamente.'
  } finally {
    loading.value = false
  }
}

const saveCourse = async () => {
  saving.value = true
  try {
    if (editingId.value) {
      await api.put(`/api/v1/courses/${editingId.value}`, form.value)
      toastSuccess('Curso atualizado com sucesso!')
    } else {
      await api.post('/api/v1/courses/', form.value)
      toastSuccess('Curso criado com sucesso!')
    }
    resetForm()
    loadCourses()
  } catch (error) {
    toastError('Erro ao salvar curso: ' + (error.response?.data?.detail || error.message))
  } finally {
    saving.value = false
  }
}

const editCourse = (course) => {
  editingId.value = course.id
  form.value = { ...course }
  showForm.value = true
}

const manageLessons = (course) => {
  router.push(`/courses/${course.id}/lessons`)
}

const viewProgress = (course) => {
  router.push(`/courses/${course.id}/progress`)
}

const confirmDelete = (course) => {
  pendingDeleteId.value = course.id
  pendingDeleteName.value = course.name
  showDeleteConfirm.value = true
}

const doDelete = async () => {
  deleting.value = true
  try {
    await api.delete(`/api/v1/courses/${pendingDeleteId.value}`)
    toastSuccess('Curso excluído com sucesso!')
    showDeleteConfirm.value = false
    loadCourses()
  } catch (error) {
    toastError('Erro ao excluir curso: ' + (error.response?.data?.detail || ''))
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
    code: '',
    name: '',
    category: '',
    carga_horaria: 0,
    price: 0,
    modality: 'PRESENCIAL',
    description: '',
    cover_image_url: '',
    cover_image_alt: '',
  }
  showForm.value = false
}

onMounted(loadCourses)
</script>
