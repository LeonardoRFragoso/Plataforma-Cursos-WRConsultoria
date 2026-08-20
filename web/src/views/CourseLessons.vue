<template>
  <div class="min-h-screen bg-gray-50">
    <AppNavbar />

    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div class="flex justify-between items-center mb-6">
        <div>
          <h1 class="text-2xl font-bold text-secondary-900">Conteúdo do Curso</h1>
          <p class="text-sm text-gray-600">{{ course.name }}</p>
        </div>
        <div class="flex gap-2">
          <AppButton @click="goToProgress" class="bg-gray-600 text-white">
            Progresso dos Alunos
          </AppButton>
          <AppButton @click="showForm = true" class="bg-primary-600 text-white">
            + Nova Aula
          </AppButton>
        </div>
      </div>

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
            <AppButton type="submit" class="bg-primary-600 text-white">
              Salvar
            </AppButton>
            <AppButton
              type="button"
              @click="resetForm"
              class="bg-gray-300 text-gray-700"
            >
              Cancelar
            </AppButton>
          </div>
        </form>
      </AppCard>

      <!-- Lista de aulas -->
      <div v-if="lessons.length === 0" class="text-center py-8">
        <p class="text-gray-600">Nenhuma aula cadastrada</p>
      </div>

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
                >▲</button>
                <button
                  v-if="index < sortedLessons.length - 1"
                  @click="moveDown(index)"
                  class="text-gray-400 hover:text-primary-600 text-xs"
                  title="Mover para baixo"
                >▼</button>
              </div>
              <div>
                <p class="font-semibold text-secondary-900">{{ lesson.order }}. {{ lesson.title }}</p>
                <div class="flex items-center gap-3 text-sm text-gray-600">
                  <span>{{ lesson.content_type }}</span>
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
            >{{ lesson.storage_key ? 'Trocar Vídeo' : 'Enviar Vídeo' }}</AppButton>
            <AppButton
              v-if="lesson.content_type === 'UPLOAD' && lesson.storage_key"
              @click="removeVideo(lesson)"
              class="bg-orange-600 text-white text-xs px-2 py-1"
            >Remover Vídeo</AppButton>
            <AppButton @click="manageMaterials(lesson)" class="bg-teal-600 text-white text-xs px-2 py-1">Materiais</AppButton>
            <AppButton @click="editLesson(lesson)" class="bg-blue-600 text-white text-xs px-2 py-1">Editar</AppButton>
            <AppButton @click="deleteLesson(lesson.id)" class="bg-red-600 text-white text-xs px-2 py-1">Deletar</AppButton>
          </div>
        </div>
      </div>

      <!-- Video Upload Modal -->
      <div v-if="videoModal.visible" class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
        <div class="bg-white rounded-lg p-6 max-w-md w-full mx-4">
          <h3 class="text-lg font-semibold mb-4">Enviar Vídeo — {{ videoModal.lessonTitle }}</h3>
          <div class="space-y-4">
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">Arquivo de vídeo</label>
              <input
                ref="videoFileInput"
                type="file"
                accept="video/mp4,video/webm,video/ogg,video/quicktime,video/mpeg"
                class="block w-full text-sm text-gray-700 file:mr-4 file:py-2 file:px-4 file:rounded-md file:border-0 file:text-sm file:font-semibold file:bg-primary-50 file:text-primary-700 hover:file:bg-primary-100"
              />
              <p class="text-xs text-gray-500 mt-1">Formatos: MP4, WebM, OGG, MOV, MPEG. Máx: 2GB</p>
            </div>
            <div v-if="videoModal.uploading" class="text-sm text-primary-600">
              Enviando vídeo... {{ videoModal.progress }}%
            </div>
            <div class="flex gap-2">
              <AppButton @click="uploadVideo" :disabled="videoModal.uploading" class="bg-primary-600 text-white">
                {{ videoModal.uploading ? 'Enviando...' : 'Enviar' }}
              </AppButton>
              <AppButton @click="closeVideoModal" class="bg-gray-300 text-gray-700">
                Cancelar
              </AppButton>
            </div>
          </div>
        </div>
      </div>

      <!-- Materials Modal -->
      <div v-if="materialsModal.visible" class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
        <div class="bg-white rounded-lg p-6 max-w-2xl w-full mx-4 max-h-[80vh] overflow-y-auto">
          <h3 class="text-lg font-semibold mb-4">Materiais — {{ materialsModal.lessonTitle }}</h3>
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
                @click="deleteMaterial(material)"
                class="text-red-600 text-xs hover:underline"
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
                />
                <p class="text-xs text-gray-500 mt-1">PDF, DOC, PPT, XLS, TXT. Máx: 100MB</p>
              </div>
              <AppButton @click="uploadMaterial" class="bg-primary-600 text-white text-sm">
                Adicionar
              </AppButton>
            </div>
          </div>
          <div class="mt-4 text-right">
            <AppButton @click="closeMaterialsModal" class="bg-gray-300 text-gray-700">
              Fechar
            </AppButton>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '../api/client'
import AppNavbar from '../components/AppNavbar.vue'
import AppCard from '../components/AppCard.vue'
import AppButton from '../components/AppButton.vue'
import AppInput from '../components/AppInput.vue'

const route = useRoute()
const router = useRouter()
const courseId = route.params.id

const course = ref({})
const lessons = ref([])
const showForm = ref(false)
const editingId = ref(null)

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

const sortedLessons = computed(() => {
  return [...lessons.value].sort((a, b) => a.order - b.order)
})

const loadCourse = async () => {
  try {
    const response = await api.get(`/api/v1/courses/${courseId}`)
    course.value = response.data
  } catch (error) {
    console.error('Erro ao carregar curso:', error)
  }
}

const loadLessons = async () => {
  try {
    const response = await api.get(`/api/v1/lessons/courses/${courseId}/lessons`)
    lessons.value = response.data
  } catch (error) {
    console.error('Erro ao carregar aulas:', error)
  }
}

const saveLesson = async () => {
  try {
    if (editingId.value) {
      await api.put(
        `/api/v1/lessons/courses/${courseId}/lessons/${editingId.value}`,
        form.value
      )
    } else {
      await api.post(`/api/v1/lessons/courses/${courseId}/lessons`, form.value)
    }
    resetForm()
    loadLessons()
  } catch (error) {
    console.error('Erro ao salvar aula:', error)
    alert('Erro ao salvar aula: ' + (error.response?.data?.detail || error.message))
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

const deleteLesson = async (id) => {
  if (!confirm('Tem certeza que deseja deletar esta aula?')) return

  try {
    await api.delete(`/api/v1/lessons/courses/${courseId}/lessons/${id}`)
    loadLessons()
  } catch (error) {
    if (error.response?.status === 409) {
      alert('Não é possível deletar esta aula: existem registros de progresso de alunos. Remova o progresso primeiro ou arquive a aula.')
    } else {
      console.error('Erro ao deletar aula:', error)
      alert('Erro ao deletar aula: ' + (error.response?.data?.detail || ''))
    }
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
    console.error('Erro ao reordenar aulas:', error)
    alert('Erro ao reordenar: ' + (error.response?.data?.detail || ''))
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
    alert('Selecione um arquivo de vídeo')
    return
  }

  const lessonId = videoModal.value.lessonId
  videoModal.value.uploading = true
  videoModal.value.progress = 0

  try {
    // Step 1: presign
    const presignResp = await api.post(`/api/v1/lessons/${lessonId}/upload-presign`, {
      filename: file.name,
      mime_type: file.type,
      size_bytes: file.size,
    })
    const { upload_url, storage_key } = presignResp.data

    // Step 2: upload to storage
    const uploadResult = await fetch(upload_url, {
      method: 'PUT',
      body: file,
      headers: { 'Content-Type': file.type },
    })

    if (!uploadResult.ok) {
      throw new Error(`Upload failed: ${uploadResult.status}`)
    }

    videoModal.value.progress = 90

    // Step 3: verify and activate
    await api.post(`/api/v1/lessons/${lessonId}/upload-complete`, null, {
      params: { storage_key }
    })

    videoModal.value.progress = 100
    closeVideoModal()
    loadLessons()
  } catch (error) {
    console.error('Erro no upload:', error)
    alert('Erro no upload do vídeo: ' + (error.response?.data?.detail || error.message))
  } finally {
    videoModal.value.uploading = false
  }
}

const removeVideo = async (lesson) => {
  if (!confirm('Remover o vídeo desta aula? O progresso dos alunos não será afetado.')) return
  try {
    await api.post(`/api/v1/lessons/${lesson.id}/remove-video`)
    loadLessons()
  } catch (error) {
    alert('Erro ao remover vídeo: ' + (error.response?.data?.detail || ''))
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
    console.error('Erro ao carregar materiais:', error)
  }
}

const uploadMaterial = async () => {
  const file = materialFileInput.value?.files?.[0]
  if (!file) {
    alert('Selecione um arquivo')
    return
  }
  if (!materialsModal.value.newTitle) {
    alert('Digite um título para o material')
    return
  }

  const lessonId = materialsModal.value.lessonId
  try {
    // Step 1: presign
    const presignResp = await api.post(`/api/v1/lessons/${lessonId}/materials/presign`, {
      filename: file.name,
      mime_type: file.type,
      size_bytes: file.size,
    })
    const { upload_url, storage_key } = presignResp.data

    // Step 2: upload to storage
    const uploadResult = await fetch(upload_url, {
      method: 'PUT',
      body: file,
      headers: { 'Content-Type': file.type },
    })

    if (!uploadResult.ok) {
      throw new Error(`Upload failed: ${uploadResult.status}`)
    }

    // Step 3: create material record
    await api.post(`/api/v1/lessons/${lessonId}/materials`, {
      title: materialsModal.value.newTitle,
    }, {
      params: {
        storage_key,
        mime_type: file.type,
        size_bytes: file.size,
      }
    })

    materialsModal.value.newTitle = ''
    if (materialFileInput.value) materialFileInput.value.value = ''
    loadMaterials()
  } catch (error) {
    console.error('Erro ao enviar material:', error)
    alert('Erro ao enviar material: ' + (error.response?.data?.detail || error.message))
  }
}

const deleteMaterial = async (material) => {
  if (!confirm('Remover este material?')) return
  try {
    await api.delete(`/api/v1/lessons/${materialsModal.value.lessonId}/materials/${material.id}`)
    loadMaterials()
  } catch (error) {
    alert('Erro ao remover material: ' + (error.response?.data?.detail || ''))
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
