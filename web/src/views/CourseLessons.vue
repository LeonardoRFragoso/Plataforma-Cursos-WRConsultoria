<template>
  <div class="min-h-screen bg-gray-50">
    <AppNavbar />

    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div class="flex flex-col md:flex-row justify-between md:items-center gap-4 mb-6">
        <div>
          <AppLink to="/courses" class="text-sm text-primary-600 hover:underline">← Cursos</AppLink>
          <h1 class="text-2xl font-bold text-secondary-900">Conteúdo do Curso</h1>
          <p class="text-sm text-gray-600">{{ course.name }} <span v-if="course.code">({{ course.code }})</span></p>
        </div>
        <AppButton @click="showForm = true" class="bg-primary-600 text-white">
          + Nova Aula
        </AppButton>
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
            <div class="md:col-span-2 flex items-center gap-2">
              <input
                v-model="form.is_free_preview"
                type="checkbox"
                id="preview"
                class="h-4 w-4 text-primary-600 border-gray-300 rounded"
              />
              <label for="preview" class="text-sm text-gray-700">Aula de amostra grátis</label>
            </div>

            <!-- URL externa -->
            <AppInput
              v-if="form.content_type !== 'UPLOAD'"
              v-model="form.video_url"
              label="URL do vídeo"
              placeholder="https://..."
              class="md:col-span-2"
            />

            <!-- Upload de arquivo -->
            <div v-if="form.content_type === 'UPLOAD'" class="md:col-span-2">
              <label class="block text-sm font-medium text-gray-700 mb-1">Arquivo de vídeo</label>
              <input
                ref="fileInput"
                type="file"
                accept="video/*"
                class="block w-full text-sm text-gray-700 file:mr-4 file:py-2 file:px-4 file:rounded-md file:border-0 file:text-sm file:font-semibold file:bg-primary-50 file:text-primary-700 hover:file:bg-primary-100"
              />
              <p v-if="uploading" class="text-sm text-primary-600 mt-2">Enviando vídeo...</p>
            </div>
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
        <AppCard
          v-for="lesson in sortedLessons"
          :key="lesson.id"
          class="flex justify-between items-center"
        >
          <div>
            <p class="font-semibold text-secondary-900">{{ lesson.order }}. {{ lesson.title }}</p>
            <p class="text-sm text-gray-600">{{ lesson.content_type }}</p>
          </div>
          <div class="flex gap-2">
            <AppButton @click="editLesson(lesson)" class="bg-blue-600 text-white text-xs px-2 py-1">Editar</AppButton>
            <AppButton @click="deleteLesson(lesson.id)" class="bg-red-600 text-white text-xs px-2 py-1">Deletar</AppButton>
          </div>
        </AppCard>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import api from '../api/client'
import AppNavbar from '../components/AppNavbar.vue'
import AppCard from '../components/AppCard.vue'
import AppLink from '../components/AppLink.vue'
import AppButton from '../components/AppButton.vue'
import AppInput from '../components/AppInput.vue'

const route = useRoute()
const courseId = route.params.id

const course = ref({})
const lessons = ref([])
const showForm = ref(false)
const editingId = ref(null)
const uploading = ref(false)

const form = ref({
  title: '',
  description: '',
  order: 0,
  content_type: 'UPLOAD',
  video_url: '',
  duration_seconds: null,
  is_free_preview: false,
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
    let lesson
    if (editingId.value) {
      const response = await api.put(
        `/api/v1/lessons/courses/${courseId}/lessons/${editingId.value}`,
        form.value
      )
      lesson = response.data
    } else {
      const response = await api.post(`/api/v1/lessons/courses/${courseId}/lessons`, form.value)
      lesson = response.data
    }

    if (form.value.content_type === 'UPLOAD' && !editingId.value) {
      await uploadVideo(lesson.id)
    }

    resetForm()
    loadLessons()
  } catch (error) {
    console.error('Erro ao salvar aula:', error)
    alert('Erro ao salvar aula: ' + (error.response?.data?.detail || error.message))
  }
}

const uploadVideo = async (lessonId) => {
  const fileInput = document.querySelector('input[type="file"]')
  const file = fileInput ? fileInput.files[0] : null
  if (!file) return

  uploading.value = true
  try {
    const uploadResponse = await api.post(`/api/v1/lessons/${lessonId}/upload-url?filename=${file.name}&content_type=${file.type}`)
    const { upload_url } = uploadResponse.data

    const uploadResult = await fetch(upload_url, {
      method: 'PUT',
      body: file,
      headers: { 'Content-Type': file.type },
    })

    if (!uploadResult.ok) {
      throw new Error(`Upload failed: ${uploadResult.status}`)
    }
  } catch (error) {
    console.error('Erro no upload:', error)
    alert('Erro no upload do vídeo: ' + error.message)
    throw error
  } finally {
    uploading.value = false
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
  }
  showForm.value = true
}

const deleteLesson = async (id) => {
  if (!confirm('Tem certeza que deseja deletar esta aula?')) return

  try {
    await api.delete(`/api/v1/lessons/courses/${courseId}/lessons/${id}`)
    loadLessons()
  } catch (error) {
    console.error('Erro ao deletar aula:', error)
    alert('Erro ao deletar aula')
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
  }
  showForm.value = false
}

onMounted(() => {
  loadCourse()
  loadLessons()
})
</script>
