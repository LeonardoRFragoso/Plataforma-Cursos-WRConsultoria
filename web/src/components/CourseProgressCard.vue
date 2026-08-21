<template>
  <div
    class="group rounded-xl border border-gray-200 bg-white shadow-sm overflow-hidden transition-all hover:shadow-md hover:-translate-y-0.5"
    :data-testid="testId"
  >
    <div class="flex gap-4 p-4">
      <!-- Cover -->
      <CourseCover
        :course="courseForCover"
        ratio="1/1"
        fit="cover"
        loading="lazy"
        wrapper-class="w-24 sm:w-28 shrink-0 rounded-lg overflow-hidden"
        img-test-id="progress-card-cover-img"
        fb-test-id="progress-card-cover-fallback"
      />

      <div class="flex-1 min-w-0 flex flex-col">
        <!-- Title + status -->
        <div class="flex items-start justify-between gap-2">
          <h3 class="font-semibold text-secondary-900 leading-snug line-clamp-2">
            {{ enrollment.course_name }}
          </h3>
          <StatusBadge
            v-if="courseState"
            :status="courseState"
            :test-id="testId + '-status'"
          />
        </div>

        <!-- Class dates -->
        <p class="mt-1 text-xs text-gray-500">
          {{ formattedDates }}
        </p>

        <!-- Progress -->
        <div class="mt-auto pt-3">
          <ProgressBar
            :value="percentage"
            :label="'Progresso'"
            :hint="progressHint"
            :show-label="true"
            size="md"
            :test-id="testId + '-progress'"
          />
        </div>

        <!-- CTAs -->
        <div class="mt-3 flex flex-wrap gap-2">
          <router-link
            :to="learnRoute"
            class="inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-offset-1 focus:ring-primary-500"
            :class="primaryCtaClass"
            :data-testid="testId + '-cta'"
          >
            <span aria-hidden="true">{{ primaryCtaIcon }}</span>
            {{ primaryCtaLabel }}
          </router-link>
          <router-link
            v-if="hasCertificate"
            :to="`/certificates`"
            class="inline-flex items-center gap-1.5 rounded-lg border border-gray-200 px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-50 transition-colors"
            :data-testid="testId + '-cert'"
          >
            <span aria-hidden="true">🏆</span>
            Certificado
          </router-link>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import api from '../api/client'
import CourseCover from './CourseCover.vue'
import ProgressBar from './ProgressBar.vue'
import StatusBadge from './StatusBadge.vue'

const props = defineProps({
  enrollment: { type: Object, required: true },
  // Optional: pass certificate course ids set to show cert CTA
  certificateCourseIds: { type: Set, default: () => new Set() },
  testId: { type: String, default: 'course-progress-card' },
})

const progress = ref(null)
const progressError = ref(false)

// Map enrollment shape → shape expected by getCourseCover().
// /enrollments/me returns course_code/course_name/cover_image_url,
// but getCourseCover() reads course.code/course.name/cover_image_url.
const courseForCover = computed(() => ({
  id: props.enrollment.course_id,
  code: props.enrollment.course_code,
  name: props.enrollment.course_name,
  category: props.enrollment.course_category,
  cover_image_url: props.enrollment.cover_image_url,
  cover_image_alt: props.enrollment.cover_image_alt,
}))

const percentage = computed(() => {
  if (progress.value && typeof progress.value.percentage === 'number') {
    return progress.value.percentage
  }
  // Derive a coarse state from enrollment status when no lesson progress yet
  if (props.enrollment.status === 'CONCLUIDA') return 100
  return 0
})

const courseState = computed(() => {
  if (props.enrollment.status === 'CONCLUIDA') return 'completed'
  if (progress.value && progress.value.percentage > 0) return 'in_progress'
  if (props.enrollment.status === 'CONFIRMADA') return 'in_progress'
  if (props.enrollment.status === 'PENDENTE') return 'not_started'
  return null
})

const hasCertificate = computed(() =>
  props.certificateCourseIds.has(props.enrollment.course_id)
)

const canPlay = computed(() =>
  props.enrollment.status === 'CONFIRMADA' || props.enrollment.status === 'CONCLUIDA'
)

const learnRoute = computed(() =>
  canPlay.value
    ? `/courses/${props.enrollment.course_id}/learn`
    : '/cursos'
)

const primaryCtaLabel = computed(() => {
  if (!canPlay.value) return 'Ver catálogo'
  if (courseState.value === 'completed') return 'Revisar curso'
  if (courseState.value === 'in_progress') return 'Continuar curso'
  return 'Começar curso'
})

const primaryCtaIcon = computed(() => {
  if (!canPlay.value) return '→'
  if (courseState.value === 'completed') return '↺'
  return '▶'
})

const primaryCtaClass = computed(() => {
  if (!canPlay.value) {
    return 'border border-gray-200 text-gray-700 hover:bg-gray-50'
  }
  return 'bg-primary-600 text-white hover:bg-primary-700'
})

const progressHint = computed(() => {
  if (progress.value && typeof progress.value.required_lessons === 'number') {
    const c = progress.value.completed_required || 0
    const r = progress.value.required_lessons || 0
    if (r > 0) return `${c} de ${r} aulas obrigatórias`
  }
  if (props.enrollment.status === 'CONCLUIDA') return 'Curso concluído'
  if (props.enrollment.status === 'PENDENTE') return 'Aguardando confirmação da matrícula'
  return ''
})

const formattedDates = computed(() => {
  const s = props.enrollment.start_date
  const e = props.enrollment.end_date
  if (!s || !e) return ''
  const months = ['jan', 'fev', 'mar', 'abr', 'mai', 'jun', 'jul', 'ago', 'set', 'out', 'nov', 'dez']
  const sd = new Date(s)
  const ed = new Date(e)
  const sameYear = sd.getFullYear() === ed.getFullYear()
  const start = `${sd.getDate()} ${months[sd.getMonth()]}`
  const end = `${ed.getDate()} ${months[ed.getMonth()]} ${ed.getFullYear()}`
  return sameYear ? `${start} — ${end}` : `${start} ${sd.getFullYear()} — ${end}`
})

const loadProgress = async () => {
  if (!canPlay.value) return
  progressError.value = false
  try {
    const { data } = await api.get(
      `/api/v1/lessons/courses/${props.enrollment.course_id}/my-progress`
    )
    progress.value = data
  } catch (e) {
    // 403/404 just means no access yet; silently keep enrollment-derived state
    progress.value = null
  }
}

watch(
  () => props.enrollment?.course_id,
  () => loadProgress(),
  { immediate: true }
)
</script>
