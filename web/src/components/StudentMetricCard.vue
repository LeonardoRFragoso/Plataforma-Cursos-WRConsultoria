<template>
  <div
    class="rounded-xl border border-gray-200 bg-white p-4 sm:p-5 shadow-sm transition-all hover:shadow-md hover:-translate-y-0.5"
    :data-testid="testId"
  >
    <div class="flex items-center gap-3">
      <div
        class="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg"
        :class="iconWrapClass"
      >
        <span class="text-lg" aria-hidden="true">{{ icon }}</span>
      </div>
      <div class="min-w-0">
        <div class="text-2xl font-bold leading-none text-secondary-900">
          {{ value }}
        </div>
        <div class="mt-1 text-xs sm:text-sm text-gray-500 truncate">{{ label }}</div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  value: { type: [Number, String], required: true },
  label: { type: String, required: true },
  icon: { type: String, default: '📚' },
  tone: { type: String, default: 'primary' }, // primary | success | warning | accent
  testId: { type: String, default: 'student-metric-card' },
})

const iconWrapClass = computed(() => ({
  primary: 'bg-primary-50 text-primary-600',
  success: 'bg-green-50 text-green-600',
  warning: 'bg-amber-50 text-amber-600',
  accent: 'bg-orange-50 text-orange-600',
}[props.tone] || 'bg-primary-50 text-primary-600'))
</script>
