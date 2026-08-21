<template>
  <div
    class="group relative rounded-xl border border-gray-200 bg-white shadow-sm overflow-hidden transition-all hover:shadow-md hover:-translate-y-0.5"
    :data-testid="testId"
  >
    <!-- Subtle course cover strip -->
    <div class="relative h-16 bg-gray-100 overflow-hidden">
      <CourseCover
        :course="courseForCover"
        ratio="16/4"
        fit="cover"
        loading="lazy"
        wrapper-class="absolute inset-0"
        img-test-id="cert-card-cover-img"
        fb-test-id="cert-card-cover-fallback"
      />
      <div class="absolute inset-0 bg-gradient-to-t from-black/40 to-transparent"></div>
      <div class="absolute top-2 left-3 text-2xl" aria-hidden="true">🏆</div>
    </div>

    <div class="p-4">
      <h3 class="font-semibold text-secondary-900 leading-snug line-clamp-2">
        {{ certificate.course_name }}
      </h3>
      <p class="mt-1 text-xs text-gray-500">
        Emitido em {{ formattedDate }}
      </p>

      <!-- Validation code -->
      <div class="mt-3 flex items-center gap-2">
        <span class="text-xs text-gray-500">Código:</span>
        <code class="font-mono text-xs bg-gray-100 px-2 py-0.5 rounded text-gray-700">
          {{ shortCode }}
        </code>
        <button
          v-if="showCopy"
          type="button"
          @click="copyCode"
          class="text-xs text-primary-600 hover:text-primary-700 font-medium"
          :data-testid="testId + '-copy'"
        >
          {{ copied ? 'Copiado!' : 'Copiar' }}
        </button>
      </div>

      <!-- Valid badge -->
      <div class="mt-3 flex items-center gap-1.5 text-xs text-green-600">
        <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
          <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd" />
        </svg>
        Certificado válido
      </div>

      <!-- Actions -->
      <div class="mt-4 flex flex-wrap gap-2">
        <button
          type="button"
          @click="download"
          class="inline-flex items-center gap-1.5 rounded-lg bg-primary-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-primary-700 transition-colors"
          :data-testid="testId + '-download'"
        >
          <span aria-hidden="true">⬇</span>
          Baixar PDF
        </button>
        <router-link
          :to="validationLink"
          class="inline-flex items-center gap-1.5 rounded-lg border border-gray-200 px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-50 transition-colors"
          :data-testid="testId + '-validate'"
        >
          <span aria-hidden="true">🔍</span>
          Validar
        </router-link>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import CourseCover from './CourseCover.vue'
import api from '../api/client'

const props = defineProps({
  certificate: { type: Object, required: true },
  showCopy: { type: Boolean, default: true },
  testId: { type: String, default: 'certificate-card' },
})

const copied = ref(false)

const courseForCover = computed(() => ({
  id: props.certificate.course_id,
  code: props.certificate.course_code,
  name: props.certificate.course_name,
  category: props.certificate.course_category,
  cover_image_url: props.certificate.cover_image_url,
  cover_image_alt: props.certificate.cover_image_alt,
}))

const formattedDate = computed(() =>
  new Date(props.certificate.issued_at).toLocaleDateString('pt-BR')
)

const shortCode = computed(() => {
  const c = props.certificate.validation_code || ''
  return c.length > 16 ? c.slice(0, 8) + '…' : c
})

const validationLink = computed(
  () => `/validar-certificado?code=${props.certificate.validation_code}`
)

const copyCode = async () => {
  try {
    await navigator.clipboard.writeText(props.certificate.validation_code)
    copied.value = true
    setTimeout(() => (copied.value = false), 1800)
  } catch {
    // clipboard not available
  }
}

const download = async () => {
  // Open the download endpoint in a new tab; the browser handles the PDF.
  const url = `/api/v1/certificates/${props.certificate.id}/download`
  // We need auth header — use axios with blob and trigger a download.
  try {
    const res = await api.get(url, { responseType: 'blob' })
    const blob = new Blob([res.data], { type: 'application/pdf' })
    const objUrl = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = objUrl
    a.download = `certificado-${props.certificate.certificate_number}.pdf`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(objUrl)
  } catch {
    // fall back to direct navigation
    window.open(url, '_blank')
  }
}
</script>
