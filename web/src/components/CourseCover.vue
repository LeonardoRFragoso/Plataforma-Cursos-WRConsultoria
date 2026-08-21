<template>
  <div
    class="course-cover relative overflow-hidden bg-gray-100"
    :class="wrapperClass"
    :style="aspectRatioStyle"
    data-testid="course-cover"
  >
    <!-- Real image (WR cover or backend-provided) -->
    <img
      v-if="!cover.isFallback && cover.src"
      :src="cover.src"
      :alt="cover.alt"
      :loading="loading"
      :width="width"
      :height="height"
      class="w-full h-full object-cover"
      :data-testid="imgTestId"
      @error="onError"
    />

    <!-- Neutral fallback: tenant-colored gradient + course code -->
    <div
      v-else
      class="w-full h-full flex flex-col items-center justify-center"
      :style="fallbackStyle"
      :data-testid="fbTestId"
    >
      <span class="text-2xl font-bold text-white/90 px-4 text-center line-clamp-2">
        {{ course?.code || '—' }}
      </span>
      <span class="text-xs text-white/70 mt-1 px-4 text-center line-clamp-1">
        {{ course?.category || '' }}
      </span>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { getCourseCover } from '../utils/courseMedia'
import { useTenantStore } from '../stores/tenant'

const props = defineProps({
  course: { type: Object, required: true },
  ratio: { type: String, default: '16/9' },
  loading: { type: String, default: 'lazy' },
  width: { type: Number, default: 1672 },
  height: { type: Number, default: 941 },
  wrapperClass: { type: String, default: '' },
  imgTestId: { type: String, default: 'course-cover-img' },
  fbTestId: { type: String, default: 'course-cover-fallback' },
})

const tenantStore = useTenantStore()
const errorFallback = ref(false)

const cover = computed(() => {
  if (errorFallback.value) {
    return { src: '', alt: props.course?.name || '', isFallback: true }
  }
  return getCourseCover(props.course)
})

const aspectRatioStyle = computed(() => ({
  aspectRatio: props.ratio,
}))

const fallbackStyle = computed(() => {
  const primary = tenantStore.primary_color || '#0056b3'
  const secondary = tenantStore.secondary_color || '#1a1a1a'
  return {
    background: `linear-gradient(135deg, ${primary}, ${secondary})`,
  }
})

// Reset error state when course changes
watch(
  () => props.course?.id,
  () => {
    errorFallback.value = false
  }
)

const onError = () => {
  errorFallback.value = true
}
</script>
