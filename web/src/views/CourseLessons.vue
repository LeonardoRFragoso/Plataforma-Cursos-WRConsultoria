<template>
  <div>
    <AppPageHeader title="Conteúdo do Curso" :description="course.name">
      <template #actions>
        <AppButton @click="goToProgress" class="bg-gray-600 text-white" data-testid="go-to-progress-btn">
          Progresso dos Alunos
        </AppButton>
        <AppButton @click="showForm = true" class="bg-primary-600 text-white" data-testid="new-lesson-btn">
          + Nova Aula
        </AppButton>
      </template>
    </AppPageHeader>

      <!-- Formulário -->
      <AppCard v-if="showForm" class="mb-8">
        <template #header>
          <h2 class="text-xl font-semibold text-secondary-900">{{ editingId ? 'Editar' : 'Nova' }} Aula</h2>
        </template>
        <form @submit.prevent="saveLesson" class="space-y-4">
          <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
            <AppInput
              v-model="form.title"
              label="Título *"
              placeholder="Título da aula"
              required
            />
            <AppInput
              v-model.number="form.order"
              label="Ordem"
              type="number"
              placeholder="0"
            />
            <div class="md:col-span-2">
              <label class="block text-sm font-medium text-gray-700 mb-1">Descrição</label>
              <textarea
                v-model="form.description"
                placeholder="Descrição da aula"
                class="w-full px-4 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500"
                rows="3"
              ></textarea>
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">Tipo de conteúdo *</label>
              <select
                v-model="form.content_type"
                class="w-full px-4 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500"
              >
                <option value="UPLOAD">Upload de vídeo</option>
                <option value="YOUTUBE">YouTube</option>
                <option value="VIMEO">Vimeo</option>
              </select>
            </div>
            <AppInput
              v-model.number="form.duration_seconds"
              label="Duração (segundos)"
              type="number"
              placeholder="300"
            />
            <div class="md:col-span-2 flex items-center gap-6">
              <div class="flex items-center gap-2">
                <input
                  v-model="form.is_free_preview"
                  type="checkbox"
                  id="preview"
                  class="h-4 w-4 text-primary-600 border-gray-300 rounded"
                />
                <label for="preview" class="text-sm text-gray-700">Aula de amostra grátis</label>
              </div>
              <div class="flex items-center gap-2">
                <input
                  v-model="form.is_required"
                  type="checkbox"
                  id="required"
                  class="h-4 w-4 text-primary-600 border-gray-300 rounded"
                />
                <label for="required" class="text-sm text-gray-700">Aula obrigatória (necessária para certificado)</label>
              </div>
            </div>

            <!-- URL externa -->
            <AppInput
              v-if="form.content_type !== 'UPLOAD'"
              v-model="form.video_url"
              label="URL do vídeo"
              placeholder="https://..."
              class="md:col-span-2"
            />
          </div>
          <div class="flex gap-2">
            <AppButton type="submit" class="bg-primary-600 text-white" :disabled="saving" data-testid="save-lesson-btn">
              {{ saving ? 'Salvando...' : 'Salvar' }}
            </AppButton>
            <AppButton
              type="button"
              @click="resetForm"
              class="bg-gray-300 text-gray-700"
              data-testid="cancel-lesson-btn"
            >
              Cancelar
            </AppButton>
          </div>
        </form>
      </AppCard>

      <!-- Loading -->
      <LoadingState v-if="loading" message="Carregando aulas..." />

      <!-- Error -->
      <AppAlert v-else-if="loadError" type="error" closable @close="loadError = ''">
        {{ loadError }}
        <button @click="loadLessons" class="underline ml-2">Tentar novamente</button>
      </AppAlert>

      <!-- Empty -->
      <EmptyState
        v-else-if="lessons.length === 0"
        title="Nenhuma aula cadastrada"
        description="Clique em '+ Nova Aula' para adicionar a primeira aula do curso."
      />

      <!-- Success list -->
      <div v-else class="space-y-3">
        <div
          v-for="(lesson, index) in sortedLessons"
          :key="lesson.id"
          class="bg-white rounded-lg shadow p-4 flex justify-between items-center"
        >
          <div class="flex-1">
            <div class="flex items-center gap-3">
              <div class="flex flex-col gap-1">
                <button
                  v-if="index > 0"
                  @click="moveUp(index)"
                  class="text-gray-400 hover:text-primary-600 text-xs"
                  title="Mover para cima"
                  :aria-label="`Mover aula ${lesson.title} para cima`"
                  data-testid="move-up-btn"
                >▲</button>
                <button
                  v-if="index < sortedLessons.length - 1"
                  @click="moveDown(index)"
                  class="text-gray-400 hover:text-primary-600 text-xs"
                  title="Mover para baixo"
                  :aria-label="`Mover aula ${lesson.title} para baixo`"
                  data-testid="move-down-btn"
                >▼</button>
              </div>
              <div>
                <p class="font-semibold text-secondary-900">{{ lesson.order }}. {{ lesson.title }}</p>
                <div class="flex items-center gap-3 text-sm text-gray-600">
                  <span>{{ formatContentType(lesson.content_type) }}</span>
                  <span v-if="lesson.is_free_preview" class="text-green-600">Grátis</span>
                  <span v-if="lesson.is_required" class="text-blue-600">Obrigatória</span>
                  <span v-else class="text-gray-400">Opcional</span>
                  <span v-if="lesson.duration_seconds" class="text-gray-500">{{ Math.floor(lesson.duration_seconds / 60) }}min</span>
                </div>
              </div>
            </div>
          </div>
          <div class="flex gap-2">
            <AppButton
              v-if="lesson.content_type === 'UPLOAD'"
              @click="manageVideo(lesson)"
              class="bg-indigo-600 text-white text-xs px-2 py-1"
              data-testid="manage-video-btn"
            >{{ lesson.storage_key ? 'Trocar Vídeo' : 'Enviar Vídeo' }}</AppButton>
            <AppButton
              v-if="lesson.content_type === 'UPLOAD' && lesson.storage_key"
              @click="confirmRemoveVideo(lesson)"
              class="bg-orange-600 text-white text-xs px-2 py-1"
              data-testid="remove-video-btn"
            >Remover Vídeo</AppButton>
            <AppButton @click="manageMaterials(lesson)" class="bg-teal-600 text-white text-xs px-2 py-1" data-testid="manage-materials-btn">Materiais</AppButton>
            <AppButton @click="editLesson(lesson)" class="bg-blue-600 text-white text-xs px-2 py-1" data-testid="edit-lesson-btn">Editar</AppButton>
            <AppButton @click="confirmDeleteLesson(lesson)" class="bg-red-600 text-white text-xs px-2 py-1" data-testid="delete-lesson-btn">Excluir</AppButton>
          </div>
        </div>
      </div>

    <!-- Video Upload Modal -->
    <AppModal v-model="videoModal.visible" :title="`Enviar Vídeo — ${videoModal.lessonTitle}`" size="md" :closable="!videoModal.uploading" :close-on-backdrop="!videoModal.uploading" @close="closeVideoModal">
      <div class="space-y-4">
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">Arquivo de vídeo</label>
          <input
            ref="videoFileInput"
            type="file"
            accept="video/mp4,video/webm,video/ogg,video/quicktime,video/mpeg"
            class="block w-full text-sm text-gray-700 file:mr-4 file:py-2 file:px-4 file:rounded-md file:border-0 file:text-sm file:font-semibold file:bg-primary-50 file:text-primary-700 hover:file:bg-primary-100"
            data-testid="video-file-input"
          />
          <p class="text-xs text-gray-500 mt-1">Formatos: MP4, WebM, OGG, MOV, MPEG. Máx: 2GB</p>
        </div>
        <div v-if="videoModal.uploading" class="text-sm text-primary-600">
          Enviando vídeo... {{ videoModal.progress }}%
        </div>
      </div>
      <template #footer>
        <button @click="closeVideoModal" :disabled="videoModal.uploading" class="px-4 py-2 rounded-md text-sm font-medium text-gray-700 bg-gray-200 hover:bg-gray-300 transition-colors disabled:opacity-50" data-testid="video-cancel-btn">
          Cancelar
        </button>
        <button @click="uploadVideo" :disabled="videoModal.uploading" class="px-4 py-2 rounded-md text-sm font-medium text-white bg-primary-600 hover:bg-primary-700 transition-colors disabled:opacity-50" data-testid="video-upload-btn">
          {{ videoModal.uploading ? 'Enviando...' : 'Enviar' }}
        </button>
      </template>
    </AppModal>

    <!-- Materials Modal -->
    <AppModal v-model="materialsModal.visible" :title="`Materiais — ${materialsModal.lessonTitle}`" size="lg" @close="closeMaterialsModal">
      <div class="space-y-3 mb-4">
        <div v-if="materialsModal.items.length === 0" class="text-gray-500 text-sm">
          Nenhum material cadastrado
        </div>
        <div
          v-for="material in materialsModal.items"
          :key="material.id"
          class="flex justify-between items-center bg-gray-50 rounded p-3"
        >
          <div>
            <p class="font-medium text-sm">{{ material.title }}</p>
            <p class="text-xs text-gray-500">{{ material.mime_type || 'arquivo' }}</p>
          </div>
          <button
            @click="confirmDeleteMaterial(material)"
            class="text-red-600 text-xs hover:underline"
            data-testid="remove-material-btn"
          >Remover</button>
        </div>
      </div>
      <div class="border-t pt-4">
        <h4 class="text-sm font-semibold mb-2">Adicionar material</h4>
        <div class="space-y-3">
          <AppInput
            v-model="materialsModal.newTitle"
            label="Título do material"
            placeholder="Apostila da aula"
          />
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">Arquivo</label>
            <input
              ref="materialFileInput"
              type="file"
              accept=".pdf,.doc,.docx,.ppt,.pptx,.xls,.xlsx,.txt"
              class="block w-full text-sm text-gray-700 file:mr-4 file:py-2 file:px-4 file:rounded-md file:border-0 file:text-sm file:font-semibold file:bg-primary-50 file:text-primary-700 hover:file:bg-primary-100"
              data-testid="material-file-input"
            />
            <p class="text-xs text-gray-500 mt-1">PDF, DOC, PPT, XLS, TXT. Máx: 100MB</p>
          </div>
        </div>
      </div>
      <template #footer>
        <button @click="closeMaterialsModal" class="px-4 py-2 rounded-md text-sm font-medium text-gray-700 bg-gray-200 hover:bg-gray-300 transition-colors" data-testid="materials-close-btn">
          Fechar
        </button>
        <button @click="uploadMaterial" :disabled="uploadingMaterial" class="px-4 py-2 rounded-md text-sm font-medium text-white bg-primary-600 hover:bg-primary-700 transition-colors disabled:opacity-50" data-testid="material-upload-btn">
          {{ uploadingMaterial ? 'Enviando...' : 'Adicionar' }}
        </button>
      </template>
    </AppModal>

    <!-- Delete lesson confirmation -->
    <ConfirmDialog
      v-model="showDeleteLessonConfirm"
      title="Excluir aula"
      :message="deleteLessonMessage"
      confirm-text="Excluir"
      cancel-text="Cancelar"
      danger
      :loading="deletingLesson"
      @confirm="doDeleteLesson"
      data-testid="delete-lesson-dialog"
    />

    <!-- Remove video confirmation -->
    <ConfirmDialog
      v-model="showRemoveVideoConfirm"
      title="Remover vídeo"
      :message="removeVideoMessage"
      confirm-text="Remover"
      cancel-text="Cancelar"
      danger
      :loading="removingVideo"
      @confirm="doRemoveVideo"
      data-testid="remove-video-dialog"
    />

    <!-- Delete material confirmation -->
    <ConfirmDialog
      v-model="showDeleteMaterialConfirm"
      title="Remover material"
      :message="deleteMaterialMessage"
      confirm-text="Remover"
      cancel-text="Cancelar"
      danger
      :loading="deletingMaterial"
      @confirm="doDeleteMaterial"
      data-testid="delete-material-dialog"
    />
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useToast } from '../composables/useToast'
import api from '../api/client'
import AppPageHeader from '../components/AppPageHeader.vue'
import AppCard from '../components/AppCard.vue'
import AppButton from '../components/AppButton.vue'
import AppInput from '../components/AppInput.vue'
import AppAlert from '../components/AppAlert.vue'
import EmptyState from '../components/EmptyState.vue'
import LoadingState from '../components/LoadingState.vue'
import AppModal from '../components/AppModal.vue'
import ConfirmDialog from '../components/ConfirmDialog.vue'

const route = useRoute()
const router = useRouter()
const { success: toastSuccess, error: toastError } = useToast()
const courseId = route.params.id

const course = ref({})
const lessons = ref([])
const showForm = ref(false)
const editingId = ref(null)
const loading = ref(false)
const saving = ref(false)
const loadError = ref('')
const uploadingMaterial = ref(false)

const videoFileInput = ref(null)
const materialFileInput = ref(null)

const form = ref({
  title: '',
  description: '',
  order: 0,
  content_type: 'UPLOAD',
  video_url: '',
  duration_seconds: null,
  is_free_preview: false,
  is_required: true,
})

const videoModal = ref({
  visible: false,
  lessonId: null,
  lessonTitle: '',
  uploading: false,
  progress: 0,
})

const materialsModal = ref({
  visible: false,
  lessonId: null,
  lessonTitle: '',
  items: [],
  newTitle: '',
})

// Delete lesson state
const showDeleteLessonConfirm = ref(false)
const deletingLesson = ref(false)
const pendingDeleteLessonId = ref(null)
const pendingDeleteLessonTitle = ref('')

// Remove video state
const showRemoveVideoConfirm = ref(false)
const removingVideo = ref(false)
const pendingRemoveVideoLesson = ref(null)

// Delete material state
const showDeleteMaterialConfirm = ref(false)
const deletingMaterial = ref(false)
const pendingDeleteMaterial = ref(null)

const sortedLessons = computed(() => {
  return [...lessons.value].sort((a, b) => a.order - b.order)
})

const deleteLessonMessage = computed(() =>
  `Excluir a aula "${pendingDeleteLessonTitle.value}"? Esta ação não pode ser desfeita.`
)

const removeVideoMessage = computed(() =>
  `Remover o vídeo da aula "${pendingRemoveVideoLesson.value?.title}"? O progresso dos alunos não será afetado.`
)

const deleteMaterialMessage = computed(() =>
  `Remover o material "${pendingDeleteMaterial.value?.title}"?`
)

const formatContentType = (type) => {
  const map = { UPLOAD: 'Upload', YOUTUBE: 'YouTube', VIMEO: 'Vimeo' }
  return map[type] || type
}

const loadCourse = async () => {
  try {
    const response = await api.get(`/api/v1/courses/${courseId}`)
    course.value = response.data
  } catch (error) {
    // silent — course name is display-only
  }
}

const loadLessons = async () => {
  loading.value = true
  loadError.value = ''
  try {
    const response = await api.get(`/api/v1/lessons/courses/${courseId}/lessons`)
    lessons.value = response.data
  } catch (error) {
    loadError.value = 'Não foi possível carregar as aulas. Tente novamente.'
  } finally {
    loading.value = false
  }
}

const saveLesson = async () => {
  saving.value = true
  try {
    if (editingId.value) {
      await api.put(
        `/api/v1/lessons/courses/${courseId}/lessons/${editingId.value}`,
        form.value
      )
      toastSuccess('Aula atualizada com sucesso!')
    } else {
      await api.post(`/api/v1/lessons/courses/${courseId}/lessons`, form.value)
      toastSuccess('Aula criada com sucesso!')
    }
    resetForm()
    loadLessons()
  } catch (error) {
    toastError('Erro ao salvar aula: ' + (error.response?.data?.detail || error.message))
  } finally {
    saving.value = false
  }
}

const editLesson = (lesson) => {
  editingId.value = lesson.id
  form.value = {
    title: lesson.title,
    description: lesson.description || '',
    order: lesson.order,
    content_type: lesson.content_type,
    video_url: lesson.video_url || '',
    duration_seconds: lesson.duration_seconds,
    is_free_preview: lesson.is_free_preview,
    is_required: lesson.is_required !== undefined ? lesson.is_required : true,
  }
  showForm.value = true
}

const confirmDeleteLesson = (lesson) => {
  pendingDeleteLessonId.value = lesson.id
  pendingDeleteLessonTitle.value = lesson.title
  showDeleteLessonConfirm.value = true
}

const doDeleteLesson = async () => {
  deletingLesson.value = true
  try {
    await api.delete(`/api/v1/lessons/courses/${courseId}/lessons/${pendingDeleteLessonId.value}`)
    toastSuccess('Aula excluída com sucesso!')
    showDeleteLessonConfirm.value = false
    loadLessons()
  } catch (error) {
    if (error.response?.status === 409) {
      toastError('Não é possível deletar esta aula: existem registros de progresso de alunos. Remova o progresso primeiro ou arquive a aula.')
    } else {
      toastError('Erro ao excluir aula: ' + (error.response?.data?.detail || ''))
    }
  } finally {
    deletingLesson.value = false
  }
}

const resetForm = () => {
  editingId.value = null
  form.value = {
    title: '',
    description: '',
    order: 0,
    content_type: 'UPLOAD',
    video_url: '',
    duration_seconds: null,
    is_free_preview: false,
    is_required: true,
  }
  showForm.value = false
}

// ─── Reorder ───

const moveUp = async (index) => {
  if (index === 0) return
  const ids = sortedLessons.value.map(l => l.id)
  ;[ids[index - 1], ids[index]] = [ids[index], ids[index - 1]]
  await reorderLessons(ids)
}

const moveDown = async (index) => {
  if (index === sortedLessons.value.length - 1) return
  const ids = sortedLessons.value.map(l => l.id)
  ;[ids[index], ids[index + 1]] = [ids[index + 1], ids[index]]
  await reorderLessons(ids)
}

const reorderLessons = async (lessonIds) => {
  try {
    const response = await api.put(
      `/api/v1/lessons/courses/${courseId}/lessons/reorder`,
      { lesson_ids: lessonIds }
    )
    lessons.value = response.data
  } catch (error) {
    toastError('Erro ao reordenar: ' + (error.response?.data?.detail || ''))
    loadLessons()
  }
}

// ─── Video Upload Lifecycle ───

const manageVideo = (lesson) => {
  videoModal.value = {
    visible: true,
    lessonId: lesson.id,
    lessonTitle: lesson.title,
    uploading: false,
    progress: 0,
  }
}

const closeVideoModal = () => {
  videoModal.value.visible = false
  videoModal.value.uploading = false
}

const uploadVideo = async () => {
  const file = videoFileInput.value?.files?.[0]
  if (!file) {
    toastError('Selecione um arquivo de vídeo')
    return
  }

  const lessonId = videoModal.value.lessonId
  videoModal.value.uploading = true
  videoModal.value.progress = 0

  try {
    const presignResp = await api.post(`/api/v1/lessons/${lessonId}/upload-presign`, {
      filename: file.name,
      mime_type: file.type,
      size_bytes: file.size,
    })
    const { upload_url, storage_key } = presignResp.data

    const uploadResult = await fetch(upload_url, {
      method: 'PUT',
      body: file,
      headers: { 'Content-Type': file.type },
    })

    if (!uploadResult.ok) {
      throw new Error(`Upload failed: ${uploadResult.status}`)
    }

    videoModal.value.progress = 90

    await api.post(`/api/v1/lessons/${lessonId}/upload-complete`, null, {
      params: { storage_key }
    })

    videoModal.value.progress = 100
    toastSuccess('Vídeo enviado com sucesso!')
    closeVideoModal()
    loadLessons()
  } catch (error) {
    toastError('Erro no upload do vídeo: ' + (error.response?.data?.detail || error.message))
  } finally {
    videoModal.value.uploading = false
  }
}

const confirmRemoveVideo = (lesson) => {
  pendingRemoveVideoLesson.value = lesson
  showRemoveVideoConfirm.value = true
}

const doRemoveVideo = async () => {
  removingVideo.value = true
  try {
    await api.post(`/api/v1/lessons/${pendingRemoveVideoLesson.value.id}/remove-video`)
    toastSuccess('Vídeo removido com sucesso!')
    showRemoveVideoConfirm.value = false
    loadLessons()
  } catch (error) {
    toastError('Erro ao remover vídeo: ' + (error.response?.data?.detail || ''))
  } finally {
    removingVideo.value = false
  }
}

// ─── Materials ───

const manageMaterials = async (lesson) => {
  materialsModal.value = {
    visible: true,
    lessonId: lesson.id,
    lessonTitle: lesson.title,
    items: [],
    newTitle: '',
  }
  await loadMaterials()
}

const closeMaterialsModal = () => {
  materialsModal.value.visible = false
}

const loadMaterials = async () => {
  try {
    const response = await api.get(`/api/v1/lessons/${materialsModal.value.lessonId}/materials`)
    materialsModal.value.items = response.data
  } catch (error) {
    // silent
  }
}

const uploadMaterial = async () => {
  const file = materialFileInput.value?.files?.[0]
  if (!file) {
    toastError('Selecione um arquivo')
    return
  }
  if (!materialsModal.value.newTitle) {
    toastError('Digite um título para o material')
    return
  }

  uploadingMaterial.value = true
  const lessonId = materialsModal.value.lessonId
  try {
    const presignResp = await api.post(`/api/v1/lessons/${lessonId}/materials/presign`, {
      filename: file.name,
      mime_type: file.type,
      size_bytes: file.size,
    })
    const { upload_url, storage_key } = presignResp.data

    const uploadResult = await fetch(upload_url, {
      method: 'PUT',
      body: file,
      headers: { 'Content-Type': file.type },
    })

    if (!uploadResult.ok) {
      throw new Error(`Upload failed: ${uploadResult.status}`)
    }

    await api.post(`/api/v1/lessons/${lessonId}/materials`, {
      title: materialsModal.value.newTitle,
    }, {
      params: {
        storage_key,
        mime_type: file.type,
        size_bytes: file.size,
      }
    })

    toastSuccess('Material adicionado com sucesso!')
    materialsModal.value.newTitle = ''
    if (materialFileInput.value) materialFileInput.value.value = ''
    loadMaterials()
  } catch (error) {
    toastError('Erro ao enviar material: ' + (error.response?.data?.detail || error.message))
  } finally {
    uploadingMaterial.value = false
  }
}

const confirmDeleteMaterial = (material) => {
  pendingDeleteMaterial.value = material
  showDeleteMaterialConfirm.value = true
}

const doDeleteMaterial = async () => {
  deletingMaterial.value = true
  try {
    await api.delete(`/api/v1/lessons/${materialsModal.value.lessonId}/materials/${pendingDeleteMaterial.value.id}`)
    toastSuccess('Material removido com sucesso!')
    showDeleteMaterialConfirm.value = false
    loadMaterials()
  } catch (error) {
    toastError('Erro ao remover material: ' + (error.response?.data?.detail || ''))
  } finally {
    deletingMaterial.value = false
  }
}

// ─── Navigation ───

const goToProgress = () => {
  router.push(`/courses/${courseId}/progress`)
}

onMounted(() => {
  loadCourse()
  loadLessons()
})
</script>
