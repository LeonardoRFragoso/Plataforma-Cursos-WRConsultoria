<template>
  <div class="min-h-screen bg-gray-50">
    <AppNavbar />

    <div v-if="notEnrolled" class="max-w-3xl mx-auto px-4 py-16 text-center">
      <h1 class="text-2xl font-bold text-secondary-900 mb-4">Acesso restrito</h1>
      <p class="text-gray-600 mb-6">Você não está matriculado neste curso. Matricule-se para assistir às aulas.</p>
      <AppLink to="/courses" class="bg-primary-600 text-white px-4 py-2 rounded-md">
        Ver cursos
      </AppLink>
    </div>

    <div v-else class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
      <div class="mb-4">
        <h1 class="text-2xl font-bold text-secondary-900">{{ course.name }}</h1>
        <p class="text-sm text-gray-600">
          Progresso do curso:
          <span data-testid="course-progress-percent">{{ progress.percentage || 0 }}%</span>
        </p>
        <p class="text-sm text-gray-600">
          Aulas obrigatórias concluídas:
          <span data-testid="course-progress-required">{{ progress.completed_required || 0 }}/{{ progress.required_lessons || 0 }}</span>
        </p>
        <div class="w-full bg-gray-200 rounded-full h-2.5 mt-2">
          <div
            class="bg-primary-600 h-2.5 rounded-full transition-all"
            :style="{ width: `${progress.percentage || 0}%` }"
          ></div>
        </div>
      </div>

      <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
        <!-- Sidebar -->
        <div class="md:col-span-1">
          <AppCard>
            <template #header>
              <h3 class="font-semibold text-secondary-900">Aulas</h3>
            </template>
            <div class="space-y-2 max-h-[70vh] overflow-y-auto pr-2">
              <button
                v-for="lesson in lessons"
                :key="lesson.id"
                data-testid="lesson-row"
                :data-lesson-id="lesson.id"
                :data-lesson-order="lesson.order"
                :data-lesson-required="lesson.is_required ? 'true' : 'false'"
                :data-lesson-completed="lesson.completed ? 'true' : 'false'"
                @click="selectLesson(lesson)"
                :class="[
                  'w-full text-left p-3 rounded-md text-sm flex items-center justify-between',
                  selectedLesson?.id === lesson.id
                    ? 'bg-primary-100 text-primary-800'
                    : 'hover:bg-gray-100 text-gray-700'
                ]"
              >
                <span class="truncate flex-1 mr-2" data-testid="lesson-title">
                  {{ lesson.order }}. {{ lesson.title }}
                </span>
                <span v-if="lesson.completed" data-testid="lesson-completed" class="text-green-600">✓</span>
                <span v-else-if="lesson.is_free_preview" class="text-xs text-primary-600">Preview</span>
                <span v-else-if="!lesson.is_required" data-testid="lesson-optional" class="text-xs text-gray-400">Opcional</span>
                <span v-else data-testid="lesson-required" class="text-xs text-gray-400">Obrigatória</span>
              </button>
              <p v-if="lessons.length === 0" class="text-gray-500 text-sm">Nenhuma aula disponível.</p>
            </div>
          </AppCard>
        </div>

        <!-- Player -->
        <div class="md:col-span-2">
          <AppCard v-if="selectedLesson">
            <template #header>
              <h2 class="font-semibold text-secondary-900">{{ selectedLesson.title }}</h2>
            </template>

            <div class="aspect-video bg-black rounded-md overflow-hidden mb-4">
              <!-- UPLOAD -->
              <video
                v-if="selectedLesson.content_type === 'UPLOAD'"
                ref="videoRef"
                :src="watchUrl"
                controls
                class="w-full h-full"
                @timeupdate="onTimeUpdate"
                @loadedmetadata="onLoaded"
                @pause="onPause"
                @ended="onEnded"
              ></video>

              <!-- YOUTUBE -->
              <iframe
                v-else-if="selectedLesson.content_type === 'YOUTUBE'"
                :src="youtubeEmbedUrl"
                class="w-full h-full"
                frameborder="0"
                allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
                allowfullscreen
              ></iframe>

              <!-- VIMEO -->
              <iframe
                v-else-if="selectedLesson.content_type === 'VIMEO'"
                :src="vimeoEmbedUrl"
                class="w-full h-full"
                frameborder="0"
                allow="autoplay; fullscreen; picture-in-picture"
                allowfullscreen
              ></iframe>

              <div v-else class="flex items-center justify-center h-full text-white">
                Tipo de conteúdo não suportado
              </div>
            </div>

            <p v-if="selectedLesson.description" class="text-gray-700 text-sm mb-4">
              {{ selectedLesson.description }}
            </p>

            <div class="flex items-center gap-3">
              <AppButton
                v-if="selectedLesson.content_type !== 'UPLOAD'"
                @click="markComplete(selectedLesson.id)"
                class="bg-primary-600 text-white"
              >
                Marcar como concluída
              </AppButton>
            </div>
          </AppCard>

          <div v-else class="text-center py-16 text-gray-500">
            Selecione uma aula para começar
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { useRoute } from 'vue-router'
import api from '../api/client'
import AppNavbar from '../components/AppNavbar.vue'
import AppCard from '../components/AppCard.vue'
import AppButton from '../components/AppButton.vue'
import AppLink from '../components/AppLink.vue'

const route = useRoute()
const courseId = route.params.id

const course = ref({})
const lessons = ref([])
const progress = ref({ percentage: 0 })
const selectedLesson = ref(null)
const watchUrl = ref(null)
const notEnrolled = ref(false)

const videoRef = ref(null)
const currentTime = ref(0)
const videoDuration = ref(0)
let progressInterval = null

const youtubeEmbedUrl = computed(() => {
  if (!selectedLesson.value?.video_url) return ''
  const match = selectedLesson.value.video_url.match(/(?:youtu\.be\/|youtube\.com\/watch\?v=|youtube\.com\/embed\/)([\w-]{11})/)
  const videoId = match ? match[1] : null
  return videoId ? `https://www.youtube.com/embed/${videoId}` : ''
})

const vimeoEmbedUrl = computed(() => {
  if (!selectedLesson.value?.video_url) return ''
  const match = selectedLesson.value.video_url.match(/vimeo\.com\/(\d+)/)
  const videoId = match ? match[1] : null
  return videoId ? `https://player.vimeo.com/video/${videoId}` : ''
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
    if (error.response?.status === 403) {
      notEnrolled.value = true
    }
  }
}

const loadProgress = async () => {
  try {
    const response = await api.get(`/api/v1/lessons/courses/${courseId}/my-progress`)
    progress.value = response.data
  } catch (error) {
    if (error.response?.status === 403) {
      notEnrolled.value = true
    }
  }
}

const selectLesson = async (lesson) => {
  if (selectedLesson.value) {
    await sendProgress(currentTime.value, false)
  }

  stopProgressTracking()
  selectedLesson.value = lesson
  currentTime.value = 0
  videoDuration.value = 0
  watchUrl.value = null

  try {
    const response = await api.get(`/api/v1/lessons/${lesson.id}/watch-url`)
    watchUrl.value = response.data.watch_url
  } catch (error) {
    console.error('Erro ao carregar URL de reprodução:', error)
    alert('Não foi possível carregar o vídeo: ' + (error.response?.data?.detail || error.message))
  }

  if (lesson.content_type === 'UPLOAD') {
    startProgressTracking()
  }
}

const onTimeUpdate = () => {
  if (videoRef.value) {
    currentTime.value = videoRef.value.currentTime
  }
}

const onLoaded = () => {
  if (videoRef.value) {
    videoDuration.value = videoRef.value.duration
  }
}

const onPause = () => {
  sendProgress(currentTime.value, false)
}

const onEnded = () => {
  if (videoDuration.value) {
    sendProgress(Math.floor(videoDuration.value), true)
  }
  loadProgress()
  loadLessons()
}

const startProgressTracking = () => {
  stopProgressTracking()
  progressInterval = setInterval(() => {
    if (videoRef.value) {
      sendProgress(videoRef.value.currentTime, false)
    }
  }, 15000)
}

const stopProgressTracking = () => {
  if (progressInterval) {
    clearInterval(progressInterval)
    progressInterval = null
  }
}

const sendProgress = async (seconds, completed) => {
  if (!selectedLesson.value) return
  try {
    await api.post(`/api/v1/lessons/${selectedLesson.value.id}/progress`, {
      watched_seconds: Math.floor(seconds || 0),
      completed: completed,
    })
    if (completed) {
      loadProgress()
      loadLessons()
    }
  } catch (error) {
    console.error('Erro ao enviar progresso:', error)
  }
}

const markComplete = async (lessonId) => {
  try {
    await api.post(`/api/v1/lessons/${lessonId}/progress`, {
      watched_seconds: 0,
      completed: true,
    })
    loadProgress()
    loadLessons()
  } catch (error) {
    console.error('Erro ao marcar aula como concluída:', error)
    alert('Erro ao marcar aula como concluída')
  }
}

onMounted(() => {
  loadCourse()
  loadLessons()
  loadProgress()
})

onBeforeUnmount(() => {
  if (selectedLesson.value) {
    sendProgress(currentTime.value, false)
  }
  stopProgressTracking()
})
</script>
