<template>
  <div>
    <div v-if="notEnrolled" class="premium-card mx-auto max-w-3xl p-10 text-center">
      <div class="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-red-50 text-red-600">
        <NavIcon name="shield" />
      </div>
      <h1 class="mt-4 text-2xl font-bold text-slate-900">Acesso restrito</h1>
      <p class="mt-2 text-sm text-slate-500">
        Você ainda não está matriculado neste curso.
      </p>
      <div class="mt-6 flex flex-col items-center justify-center gap-3 sm:flex-row">
        <button
          type="button"
          data-testid="demo-enroll-button"
          class="rounded-xl bg-[var(--brand-primary)] px-5 py-2.5 text-sm font-bold text-white disabled:cursor-not-allowed disabled:opacity-60"
          :disabled="demoEnrolling"
          @click="activateDemoAccess"
        >
          {{ demoEnrolling ? 'Ativando acesso…' : 'Ativar acesso de demonstração' }}
        </button>
        <AppLink to="/cursos" class="rounded-xl border border-slate-200 px-5 py-2.5 text-sm font-bold text-slate-700">
          Ver catálogo
        </AppLink>
      </div>
      <p class="mt-4 text-xs text-slate-400">
        A ativação acima existe apenas no ambiente de homologação e não realiza cobrança.
      </p>
    </div>

    <div v-else class="w-full space-y-5">
      <section class="premium-card overflow-hidden">
        <div class="flex flex-col gap-4 p-4 sm:flex-row sm:items-center sm:p-5">
          <CourseCover
            :course="course"
            ratio="16/9"
            fit="cover"
            loading="lazy"
            wrapper-class="w-full sm:w-32 sm:h-20 shrink-0 rounded-xl overflow-hidden"
            img-test-id="courselearn-context-img"
            fb-test-id="courselearn-context-fallback"
          />
          <div class="min-w-0 flex-1">
            <div class="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
              <div>
                <p class="premium-kicker">Sala de aula</p>
                <h1 class="mt-1 truncate text-xl font-bold text-slate-900 sm:text-2xl">{{ course.name }}</h1>
              </div>
              <div class="text-left sm:text-right">
                <p class="text-xs text-slate-400">Progresso do curso</p>
                <p class="text-lg font-black text-slate-900" data-testid="course-progress-percent">
                  {{ progress.percentage || 0 }}%
                </p>
              </div>
            </div>
            <div class="mt-3 h-2 overflow-hidden rounded-full bg-slate-100">
              <div
                class="h-full rounded-full transition-all duration-500"
                :style="{ width: `${progress.percentage || 0}%`, background: 'var(--brand-primary)' }"
              />
            </div>
            <p class="mt-2 text-xs text-slate-400">
              Aulas obrigatórias concluídas:
              <span class="font-bold text-slate-600" data-testid="course-progress-required">
                {{ progress.completed_required || 0 }}/{{ progress.required_lessons || 0 }}
              </span>
            </p>
          </div>
        </div>
      </section>

      <div class="grid grid-cols-1 gap-5 lg:grid-cols-[320px_1fr]">
        <aside class="premium-card h-fit overflow-hidden lg:sticky lg:top-28">
          <div class="border-b border-slate-100 px-4 py-4">
            <p class="premium-kicker">Conteúdo</p>
            <h3 class="mt-1 font-bold text-slate-900">Aulas do curso</h3>
          </div>
          <div class="max-h-[68vh] space-y-1 overflow-y-auto p-2">
            <button
              v-for="lesson in lessons"
              :key="lesson.id"
              type="button"
              data-testid="lesson-row"
              :data-lesson-id="lesson.id"
              :data-lesson-order="lesson.order"
              :data-lesson-required="lesson.is_required ? 'true' : 'false'"
              :data-lesson-completed="lesson.completed ? 'true' : 'false'"
              :class="[
                'flex w-full items-center gap-3 rounded-xl p-3 text-left text-sm transition',
                selectedLesson?.id === lesson.id
                  ? 'bg-[var(--brand-primary-soft)] text-slate-900'
                  : 'text-slate-600 hover:bg-slate-50',
              ]"
              @click="selectLesson(lesson)"
            >
              <span
                :class="[
                  'flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-xs font-black',
                  lesson.completed
                    ? 'bg-emerald-100 text-emerald-700'
                    : selectedLesson?.id === lesson.id
                      ? 'bg-white text-[var(--brand-primary)]'
                      : 'bg-slate-100 text-slate-500',
                ]"
              >
                {{ lesson.completed ? '✓' : lesson.order }}
              </span>
              <span class="min-w-0 flex-1 truncate font-semibold" data-testid="lesson-title">{{ lesson.title }}</span>
              <span v-if="lesson.completed" data-testid="lesson-completed" class="sr-only">Concluída</span>
              <span v-else-if="lesson.is_free_preview" class="text-[10px] font-bold text-[var(--brand-primary)]">Preview</span>
              <span v-else-if="!lesson.is_required" data-testid="lesson-optional" class="text-[10px] text-slate-400">Opcional</span>
              <span v-else data-testid="lesson-required" class="text-[10px] text-slate-400">Obrigatória</span>
            </button>
            <p v-if="lessons.length === 0" class="p-6 text-center text-sm text-slate-400">Nenhuma aula disponível.</p>
          </div>
        </aside>

        <main class="min-w-0">
          <div v-if="selectedLesson" class="premium-card overflow-hidden">
            <div class="border-b border-slate-100 px-5 py-4">
              <p class="text-[10px] font-bold uppercase tracking-[.15em] text-[var(--brand-primary)]">
                Aula {{ selectedLesson.order }}
              </p>
              <h2 class="mt-1 font-bold text-slate-900">{{ selectedLesson.title }}</h2>
            </div>
            <div class="bg-slate-950 p-2 sm:p-3">
              <div class="aspect-video overflow-hidden rounded-xl bg-black shadow-2xl">
                <video
                  v-if="selectedLesson.content_type === 'UPLOAD'"
                  ref="videoRef"
                  :src="watchUrl"
                  controls
                  class="h-full w-full"
                  @timeupdate="onTimeUpdate"
                  @loadedmetadata="onLoaded"
                  @pause="onPause"
                  @ended="onEnded"
                />
                <iframe
                  v-else-if="selectedLesson.content_type === 'YOUTUBE'"
                  :src="youtubeEmbedUrl"
                  class="h-full w-full"
                  frameborder="0"
                  allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
                  allowfullscreen
                />
                <iframe
                  v-else-if="selectedLesson.content_type === 'VIMEO'"
                  :src="vimeoEmbedUrl"
                  class="h-full w-full"
                  frameborder="0"
                  allow="autoplay; fullscreen; picture-in-picture"
                  allowfullscreen
                />
                <div v-else class="flex h-full items-center justify-center text-sm text-white/70">
                  Tipo de conteúdo não suportado
                </div>
              </div>
            </div>
            <div class="p-5">
              <p v-if="selectedLesson.description" class="text-sm leading-6 text-slate-500">
                {{ selectedLesson.description }}
              </p>
              <div class="mt-4 flex flex-wrap items-center gap-3">
                <button
                  v-if="selectedLesson.content_type !== 'UPLOAD'"
                  type="button"
                  class="rounded-xl bg-[var(--brand-primary)] px-4 py-2.5 text-sm font-bold text-white"
                  @click="markComplete(selectedLesson.id)"
                >
                  Marcar como concluída
                </button>
                <button
                  v-if="nextLesson"
                  type="button"
                  class="rounded-xl border border-slate-200 px-4 py-2.5 text-sm font-bold text-slate-700"
                  @click="selectLesson(nextLesson)"
                >
                  Próxima aula
                </button>
              </div>
            </div>
          </div>
          <div v-else class="premium-card flex min-h-[380px] items-center justify-center p-10 text-center">
            <div>
              <div class="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-[var(--brand-primary-soft)] text-[var(--brand-primary)]">
                <NavIcon name="catalog" />
              </div>
              <p class="mt-4 font-bold text-slate-800">Selecione uma aula para começar</p>
              <p class="mt-1 text-sm text-slate-400">Seu progresso é salvo automaticamente.</p>
            </div>
          </div>
        </main>
      </div>

      <section v-if="assessment.required" class="premium-card overflow-hidden" data-testid="final-assessment-card">
        <div class="border-b border-slate-100 px-5 py-5">
          <p class="premium-kicker">Etapa final</p>
          <div class="mt-1 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <h2 class="text-xl font-bold text-slate-900">Avaliação de aprendizagem</h2>
              <p class="mt-1 text-sm text-slate-500">
                A avaliação é liberada após a conclusão de todas as aulas obrigatórias.
              </p>
            </div>
            <span class="w-fit rounded-full bg-slate-100 px-3 py-1 text-xs font-bold text-slate-600">
              Nota mínima demo: {{ assessment.minimum_score || 60 }}%
            </span>
          </div>
        </div>

        <div class="p-5 sm:p-6">
          <div v-if="assessment.certificate_id || certificateResult" class="rounded-2xl border border-emerald-200 bg-emerald-50 p-5" data-testid="certificate-issued-state">
            <p class="text-sm font-black uppercase tracking-wide text-emerald-700">Jornada concluída</p>
            <h3 class="mt-2 text-xl font-bold text-slate-900">Certificado demo emitido</h3>
            <p class="mt-2 text-sm leading-6 text-slate-600">
              A emissão desta homologação permanece identificada como demonstração e sem validade oficial.
            </p>
            <p v-if="certificateResult?.certificate_number" class="mt-3 text-sm font-semibold text-slate-700">
              Número: {{ certificateResult.certificate_number }}
            </p>
            <div class="mt-5 flex flex-wrap gap-3">
              <AppLink to="/certificates" class="rounded-xl bg-[var(--brand-primary)] px-4 py-2.5 text-sm font-bold text-white">
                Ver meus certificados
              </AppLink>
              <AppLink
                v-if="certificateValidationCode"
                :to="`/validar-certificado?codigo=${encodeURIComponent(certificateValidationCode)}`"
                class="rounded-xl border border-emerald-300 bg-white px-4 py-2.5 text-sm font-bold text-emerald-800"
              >
                Validar certificado
              </AppLink>
            </div>
          </div>

          <div v-else-if="!assessment.lessons_complete" class="rounded-2xl border border-amber-200 bg-amber-50 p-5">
            <p class="font-bold text-amber-900">Conclua as aulas antes da prova.</p>
            <p class="mt-1 text-sm text-amber-800/80">
              Progresso atual: {{ progress.completed_required || 0 }}/{{ progress.required_lessons || 0 }} aulas obrigatórias.
            </p>
          </div>

          <div v-else-if="assessmentResult && !assessmentResult.passed" class="rounded-2xl border border-red-200 bg-red-50 p-5" data-testid="assessment-failed-state">
            <p class="text-sm font-black uppercase tracking-wide text-red-700">Resultado insatisfatório</p>
            <p class="mt-2 text-2xl font-black text-slate-900">{{ assessmentResult.score }}%</p>
            <p class="mt-1 text-sm text-slate-600">
              Você acertou {{ assessmentResult.correct_answers }} de {{ assessmentResult.total_questions }} questões. Revise o conteúdo e tente novamente.
            </p>
            <button
              type="button"
              class="mt-4 rounded-xl bg-[var(--brand-primary)] px-4 py-2.5 text-sm font-bold text-white disabled:opacity-60"
              :disabled="assessmentBusy"
              @click="retryAssessment"
            >
              Nova tentativa
            </button>
          </div>

          <div v-else-if="assessmentResult?.passed || assessment.passed" class="space-y-5" data-testid="assessment-passed-state">
            <div class="rounded-2xl border border-emerald-200 bg-emerald-50 p-5">
              <p class="text-sm font-black uppercase tracking-wide text-emerald-700">Resultado satisfatório</p>
              <p class="mt-2 text-2xl font-black text-slate-900">
                {{ assessmentResult?.score ?? assessment.best_score }}%
              </p>
              <p class="mt-1 text-sm text-slate-600">
                Falta apenas confirmar sua identidade e a conclusão deste treinamento.
              </p>
            </div>

            <div class="rounded-2xl border border-slate-200 p-5">
              <label class="flex items-start gap-3 text-sm leading-6 text-slate-700">
                <input v-model="declarationAccepted" type="checkbox" class="mt-1 h-4 w-4" />
                <span>
                  Declaro que fui eu quem realizou esta capacitação e avaliação e confirmo a conclusão do treinamento.
                </span>
              </label>
              <label class="mt-4 block text-sm font-bold text-slate-700" for="completion-password">
                Confirme sua senha
              </label>
              <input
                id="completion-password"
                v-model="confirmationPassword"
                type="password"
                autocomplete="current-password"
                class="mt-2 w-full max-w-md rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm outline-none focus:border-[var(--brand-primary)]"
                placeholder="Digite sua senha"
              />
              <p v-if="confirmationError" class="mt-2 text-sm font-semibold text-red-600">{{ confirmationError }}</p>
              <button
                type="button"
                data-testid="confirm-completion-button"
                class="mt-4 rounded-xl bg-[var(--brand-primary)] px-5 py-2.5 text-sm font-bold text-white disabled:cursor-not-allowed disabled:opacity-60"
                :disabled="confirmationBusy || !declarationAccepted || !confirmationPassword"
                @click="confirmCompletion"
              >
                {{ confirmationBusy ? 'Confirmando…' : 'Confirmar e emitir certificado demo' }}
              </button>
            </div>
          </div>

          <form v-else-if="assessmentSession" class="space-y-6" @submit.prevent="submitAssessment">
            <div class="flex flex-wrap items-center justify-between gap-3">
              <p class="text-sm font-bold text-slate-700">Tentativa {{ assessmentSession.attempt_number }}</p>
              <p class="text-xs text-slate-400">Responda todas as questões antes de enviar.</p>
            </div>
            <fieldset
              v-for="(question, qIndex) in assessmentSession.questions"
              :key="question.id"
              class="rounded-2xl border border-slate-200 p-5"
            >
              <legend class="px-2 text-sm font-bold text-slate-900">
                {{ qIndex + 1 }}. {{ question.prompt }}
              </legend>
              <div class="mt-3 space-y-2">
                <label
                  v-for="(option, optionIndex) in question.options"
                  :key="`${question.id}-${optionIndex}`"
                  class="flex cursor-pointer items-start gap-3 rounded-xl border border-slate-100 px-4 py-3 text-sm text-slate-700 hover:bg-slate-50"
                >
                  <input
                    v-model="assessmentAnswers[question.id]"
                    type="radio"
                    :name="question.id"
                    :value="optionIndex"
                    class="mt-0.5 h-4 w-4"
                  />
                  <span>{{ option }}</span>
                </label>
              </div>
            </fieldset>
            <p v-if="assessmentError" class="text-sm font-semibold text-red-600">{{ assessmentError }}</p>
            <button
              type="submit"
              data-testid="assessment-submit-button"
              class="rounded-xl bg-[var(--brand-primary)] px-5 py-2.5 text-sm font-bold text-white disabled:cursor-not-allowed disabled:opacity-60"
              :disabled="assessmentBusy"
            >
              {{ assessmentBusy ? 'Enviando…' : 'Enviar avaliação' }}
            </button>
          </form>

          <div v-else>
            <p class="text-sm leading-6 text-slate-600">
              Você concluiu as aulas obrigatórias. Inicie a avaliação final para registrar o resultado da aprendizagem.
            </p>
            <button
              type="button"
              data-testid="assessment-start-button"
              class="mt-4 rounded-xl bg-[var(--brand-primary)] px-5 py-2.5 text-sm font-bold text-white disabled:cursor-not-allowed disabled:opacity-60"
              :disabled="assessmentBusy"
              @click="startAssessment"
            >
              {{ assessmentBusy ? 'Preparando…' : 'Iniciar avaliação final' }}
            </button>
            <p v-if="assessmentError" class="mt-2 text-sm font-semibold text-red-600">{{ assessmentError }}</p>
          </div>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import api from '../api/client'
import { useToast } from '../composables/useToast'
import CourseCover from '../components/CourseCover.vue'
import AppLink from '../components/AppLink.vue'
import NavIcon from '../components/NavIcon.vue'

const route = useRoute()
const { error: toastError } = useToast()
const courseId = route.params.id

const course = ref({})
const lessons = ref([])
const progress = ref({ percentage: 0, completed_required: 0, required_lessons: 0 })
const assessment = ref({ required: false, lessons_complete: false, minimum_score: 60, passed: false })
const selectedLesson = ref(null)
const watchUrl = ref(null)
const notEnrolled = ref(false)
const demoEnrolling = ref(false)
const videoRef = ref(null)
const currentTime = ref(0)
const videoDuration = ref(0)

const assessmentSession = ref(null)
const assessmentAnswers = ref({})
const assessmentResult = ref(null)
const assessmentBusy = ref(false)
const assessmentError = ref('')
const passedAttemptId = ref(null)
const declarationAccepted = ref(false)
const confirmationPassword = ref('')
const confirmationBusy = ref(false)
const confirmationError = ref('')
const certificateResult = ref(null)

let progressInterval = null

const youtubeEmbedUrl = computed(() => {
  if (!selectedLesson.value?.video_url) return ''
  const match = selectedLesson.value.video_url.match(/(?:youtu\.be\/|youtube\.com\/watch\?v=|youtube\.com\/embed\/)([\w-]{11})/)
  return match ? `https://www.youtube.com/embed/${match[1]}` : ''
})

const vimeoEmbedUrl = computed(() => {
  if (!selectedLesson.value?.video_url) return ''
  const match = selectedLesson.value.video_url.match(/vimeo\.com\/(\d+)/)
  return match ? `https://player.vimeo.com/video/${match[1]}` : ''
})

const nextLesson = computed(() => {
  if (!selectedLesson.value) return lessons.value[0] || null
  const ordered = [...lessons.value].sort((a, b) => a.order - b.order)
  const index = ordered.findIndex((lesson) => lesson.id === selectedLesson.value.id)
  return index >= 0 ? ordered[index + 1] || null : null
})

const certificateValidationCode = computed(
  () => certificateResult.value?.validation_code || assessment.value.certificate_validation_code || null,
)

const loadCourse = async () => {
  try {
    course.value = (await api.get(`/api/v1/courses/${courseId}`)).data
  } catch {
    // The page keeps its neutral state if course metadata cannot be loaded.
  }
}

const loadLessons = async () => {
  try {
    lessons.value = (await api.get(`/api/v1/lessons/courses/${courseId}/lessons`)).data
  } catch (error) {
    if (error.response?.status === 403) notEnrolled.value = true
  }
}

const loadProgress = async () => {
  try {
    progress.value = (await api.get(`/api/v1/lessons/courses/${courseId}/my-progress`)).data
  } catch (error) {
    if (error.response?.status === 403) notEnrolled.value = true
  }
}

const loadAssessment = async () => {
  try {
    const response = await api.get(`/api/v1/assessments/courses/${courseId}/status`)
    assessment.value = response.data
    if (response.data.passed_attempt_id) passedAttemptId.value = response.data.passed_attempt_id
    notEnrolled.value = false
  } catch (error) {
    if (error.response?.status === 403) {
      notEnrolled.value = true
      return
    }
    if (error.response?.status !== 404) {
      assessmentError.value = error.response?.data?.detail || 'Não foi possível carregar a avaliação.'
    }
  }
}

const reloadStudentJourney = async () => {
  await Promise.all([loadLessons(), loadProgress(), loadAssessment()])
}

const activateDemoAccess = async () => {
  demoEnrolling.value = true
  try {
    await api.post(`/api/v1/assessments/courses/${courseId}/demo-enroll`)
    notEnrolled.value = false
    await reloadStudentJourney()
    if (lessons.value.length && !selectedLesson.value) await selectLesson(lessons.value[0])
  } catch (error) {
    toastError(error.response?.data?.detail || 'Não foi possível ativar o acesso de demonstração.')
  } finally {
    demoEnrolling.value = false
  }
}

const selectLesson = async (lesson) => {
  if (selectedLesson.value) await sendProgress(currentTime.value, false)
  stopProgressTracking()
  selectedLesson.value = lesson
  currentTime.value = 0
  videoDuration.value = 0
  watchUrl.value = null
  try {
    watchUrl.value = (await api.get(`/api/v1/lessons/${lesson.id}/watch-url`)).data.watch_url
  } catch (error) {
    toastError(`Não foi possível carregar o vídeo: ${error.response?.data?.detail || error.message}`)
  }
  if (lesson.content_type === 'UPLOAD') startProgressTracking()
}

const onTimeUpdate = () => {
  if (videoRef.value) currentTime.value = videoRef.value.currentTime
}

const onLoaded = () => {
  if (videoRef.value) videoDuration.value = videoRef.value.duration
}

const onPause = () => sendProgress(currentTime.value, false)

const onEnded = async () => {
  if (videoDuration.value) await sendProgress(Math.floor(videoDuration.value), true)
  await reloadStudentJourney()
}

const startProgressTracking = () => {
  stopProgressTracking()
  progressInterval = setInterval(() => {
    if (videoRef.value) sendProgress(videoRef.value.currentTime, false)
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
  const payload = { watched_seconds: Math.floor(seconds || 0), completed }
  const endpoint = assessment.value.required
    ? `/api/v1/assessments/lessons/${selectedLesson.value.id}/progress`
    : `/api/v1/lessons/${selectedLesson.value.id}/progress`
  try {
    await api.post(endpoint, payload)
    if (completed) await Promise.all([loadProgress(), loadLessons(), loadAssessment()])
  } catch {
    // Playback remains available; the next heartbeat retries progress persistence.
  }
}

const markComplete = async (lessonId) => {
  try {
    const endpoint = assessment.value.required
      ? `/api/v1/assessments/lessons/${lessonId}/progress`
      : `/api/v1/lessons/${lessonId}/progress`
    await api.post(endpoint, { watched_seconds: 0, completed: true })
    await reloadStudentJourney()
  } catch {
    toastError('Erro ao marcar aula como concluída.')
  }
}

const startAssessment = async () => {
  assessmentBusy.value = true
  assessmentError.value = ''
  assessmentResult.value = null
  try {
    assessmentSession.value = (await api.post(`/api/v1/assessments/courses/${courseId}/start`)).data
    assessmentAnswers.value = {}
  } catch (error) {
    assessmentError.value = error.response?.data?.detail || 'Não foi possível iniciar a avaliação.'
  } finally {
    assessmentBusy.value = false
  }
}

const submitAssessment = async () => {
  if (!assessmentSession.value) return
  const missing = assessmentSession.value.questions.some(
    (question) => !Object.prototype.hasOwnProperty.call(assessmentAnswers.value, question.id),
  )
  if (missing) {
    assessmentError.value = 'Responda todas as questões antes de enviar.'
    return
  }
  assessmentBusy.value = true
  assessmentError.value = ''
  try {
    assessmentResult.value = (
      await api.post(`/api/v1/assessments/attempts/${assessmentSession.value.attempt_id}/submit`, {
        answers: assessmentAnswers.value,
      })
    ).data
    if (assessmentResult.value.passed) passedAttemptId.value = assessmentResult.value.attempt_id
    assessmentSession.value = null
    await loadAssessment()
  } catch (error) {
    assessmentError.value = error.response?.data?.detail || 'Não foi possível enviar a avaliação.'
  } finally {
    assessmentBusy.value = false
  }
}

const retryAssessment = async () => {
  assessmentResult.value = null
  await startAssessment()
}

const confirmCompletion = async () => {
  const attemptId = assessmentResult.value?.attempt_id || passedAttemptId.value || assessment.value.passed_attempt_id
  if (!attemptId) {
    confirmationError.value = 'Não foi possível identificar a tentativa aprovada. Atualize a página e tente novamente.'
    return
  }
  confirmationBusy.value = true
  confirmationError.value = ''
  try {
    certificateResult.value = (
      await api.post(`/api/v1/assessments/attempts/${attemptId}/confirm`, {
        password: confirmationPassword.value,
        declaration_accepted: declarationAccepted.value,
      })
    ).data
    confirmationPassword.value = ''
    await Promise.all([loadAssessment(), loadProgress()])
  } catch (error) {
    confirmationError.value = error.response?.data?.detail || 'Não foi possível confirmar a conclusão.'
  } finally {
    confirmationBusy.value = false
  }
}

onMounted(async () => {
  await loadCourse()
  await Promise.all([loadLessons(), loadProgress(), loadAssessment()])
})

onBeforeUnmount(() => {
  if (selectedLesson.value) sendProgress(currentTime.value, false)
  stopProgressTracking()
})
</script>
