<template>
  <div class="space-y-4">
    <!-- Core facts -->
    <div class="space-y-3 text-sm bg-white rounded-lg p-4 border border-gray-100">
      <div class="flex justify-between gap-2">
        <span class="text-gray-500">Número</span>
        <span class="font-semibold text-gray-900 text-right">{{ certNumber }}</span>
      </div>
      <div class="flex justify-between gap-2">
        <span class="text-gray-500">Aluno</span>
        <span class="font-semibold text-gray-900 text-right">{{ studentName }}</span>
      </div>
      <div class="flex justify-between gap-2">
        <span class="text-gray-500">Curso</span>
        <span class="font-semibold text-gray-900 text-right">{{ courseName }}</span>
      </div>
      <div v-if="courseCode" class="flex justify-between gap-2">
        <span class="text-gray-500">Código do curso</span>
        <span class="font-semibold text-gray-900 text-right">{{ courseCode }}</span>
      </div>
      <div v-if="courseCategory" class="flex justify-between gap-2">
        <span class="text-gray-500">Categoria</span>
        <span class="font-semibold text-gray-900 text-right">{{ courseCategory }}</span>
      </div>
      <div v-if="workloadHours != null" class="flex justify-between gap-2">
        <span class="text-gray-500">Carga horária</span>
        <span class="font-semibold text-gray-900 text-right">{{ workloadHours }}h</span>
      </div>
      <div v-if="modality" class="flex justify-between gap-2">
        <span class="text-gray-500">Modalidade</span>
        <span class="font-semibold text-gray-900 text-right">{{ modality }}</span>
      </div>
      <div class="flex justify-between gap-2">
        <span class="text-gray-500">Emitido em</span>
        <span class="font-semibold text-gray-900 text-right">{{ formatDate(issuedAt) }}</span>
      </div>
      <div v-if="expiresAt" class="flex justify-between gap-2">
        <span class="text-gray-500">Válido até</span>
        <span class="font-semibold text-gray-900 text-right">{{ formatDate(expiresAt) }}</span>
      </div>
      <div v-if="version != null" class="flex justify-between gap-2">
        <span class="text-gray-500">Versão</span>
        <span class="font-semibold text-gray-900 text-right">{{ version }}</span>
      </div>
    </div>

    <!-- Academic journey -->
    <div v-if="journey && journey.steps && journey.steps.length" class="bg-white rounded-lg p-4 border border-gray-100" data-testid="validate-journey">
      <h3 class="text-sm font-bold text-gray-900 mb-1">Jornada até a emissão</h3>
      <p v-if="journey.progress" class="text-xs text-gray-500 mb-3">
        {{ journey.progress.required_lessons_completed }} de
        {{ journey.progress.required_lessons_total }} aulas obrigatórias
        ({{ journey.progress.completion_percent }}%)
      </p>
      <ol class="relative border-l-2 border-primary-200 ml-2 space-y-3">
        <li
          v-for="step in journey.steps"
          :key="step.type + '-' + step.order"
          class="ml-4"
          :data-testid="`journey-step-${step.type}`"
        >
          <span class="absolute -left-[7px] flex items-center justify-center w-3.5 h-3.5 bg-primary-600 rounded-full ring-2 ring-white"></span>
          <p class="text-sm font-medium text-gray-900">{{ step.label }}</p>
          <p v-if="step.occurred_at" class="text-xs text-gray-500">{{ formatDate(step.occurred_at) }}</p>
          <p v-else-if="step.description" class="text-xs text-gray-400 italic">{{ step.description }}</p>
        </li>
      </ol>

      <!-- Expandable per-lesson detail -->
      <div v-if="journey.lessons && journey.lessons.length" class="mt-3">
        <button
          type="button"
          class="text-xs font-medium text-primary-700 hover:text-primary-800 underline"
          @click="showLessons = !showLessons"
          :aria-expanded="showLessons"
          data-testid="validate-toggle-lessons"
        >
          {{ showLessons ? 'Ocultar detalhes das aulas' : 'Ver detalhes das aulas' }}
        </button>
        <ul v-if="showLessons" class="mt-2 space-y-1 text-xs text-gray-600" data-testid="validate-lessons-list">
          <li v-for="(lesson, idx) in journey.lessons" :key="idx" class="flex items-center gap-2">
            <svg class="w-3.5 h-3.5 text-green-600 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
              <path fill-rule="evenodd" d="M16.704 4.153a.75.75 0 01.143 1.052l-8 10.5a.75.75 0 01-1.127.075l-4.5-4.5a.75.75 0 011.06-1.06l3.894 3.893 7.48-9.817a.75.75 0 011.05-.143z" clip-rule="evenodd" />
            </svg>
            <span>{{ lesson.label }}</span>
            <span v-if="lesson.occurred_at" class="text-gray-400">— {{ formatDate(lesson.occurred_at) }}</span>
          </li>
        </ul>
      </div>
    </div>

    <!-- Integrity -->
    <div class="bg-white rounded-lg p-4 border border-gray-100" data-testid="validate-integrity">
      <div class="flex items-center gap-2 text-sm text-gray-700">
        <svg class="w-5 h-5 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
          <path stroke-linecap="round" stroke-linejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
        <span>Integridade digital verificada</span>
      </div>
      <button
        type="button"
        class="mt-2 text-xs font-medium text-gray-500 hover:text-gray-700 underline"
        @click="showTech = !showTech"
        :aria-expanded="showTech"
        data-testid="validate-toggle-tech"
      >
        {{ showTech ? 'Ocultar detalhes técnicos' : 'Detalhes técnicos' }}
      </button>
      <div v-if="showTech" class="mt-2 space-y-1 text-xs text-gray-500 break-all" data-testid="validate-tech-details">
        <p><span class="font-medium text-gray-600">Hash do registro:</span> {{ contentHash || '—' }}</p>
        <p><span class="font-medium text-gray-600">Versão:</span> {{ version ?? '—' }}</p>
        <p><span class="font-medium text-gray-600">Código de validação:</span> {{ validationCode || '—' }}</p>
        <p><span class="font-medium text-gray-600">Número:</span> {{ certNumber || '—' }}</p>
        <p class="text-gray-400 italic mt-1">O hash acima é do registro de emissão, não do arquivo PDF.</p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'

const props = defineProps({
  result: { type: Object, required: true },
  formatDate: { type: Function, required: true },
})

const showLessons = ref(false)
const showTech = ref(false)

// Support both nested (new) and flat (backwards-compatible) response shapes.
const cert = computed(() => props.result.certificate || {})
const student = computed(() => props.result.student || {})
const course = computed(() => props.result.course || {})
const journey = computed(() => props.result.journey || null)

const certNumber = computed(() => cert.value.number || props.result.certificate_number)
const validationCode = computed(() => cert.value.validation_code || props.result.validation_code)
const version = computed(() => cert.value.version ?? props.result.version)
const contentHash = computed(() => cert.value.content_hash ?? props.result.content_hash)
const issuedAt = computed(() => cert.value.issued_at || props.result.issued_at)
const expiresAt = computed(() => cert.value.expires_at ?? props.result.expires_at)
const studentName = computed(() => student.value.name || props.result.student_name)
const courseName = computed(() => course.value.name || props.result.course_name)
const courseCode = computed(() => course.value.code)
const courseCategory = computed(() => course.value.category)
const workloadHours = computed(() => course.value.workload_hours)
const modality = computed(() => course.value.modality)
</script>
