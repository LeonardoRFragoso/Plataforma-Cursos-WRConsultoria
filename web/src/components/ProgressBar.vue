<template>
  <div class="w-full" :data-testid="testId">
    <div
      v-if="showLabel"
      class="flex items-center justify-between mb-1 text-xs"
      :class="labelClass"
    >
      <span class="font-medium text-gray-600">{{ label }}</span>
      <span class="font-semibold" :class="valueColorClass">{{ Math.round(clamped) }}%</span>
    </div>
    <div
      class="w-full rounded-full bg-gray-200 overflow-hidden"
      :class="trackClass"
      role="progressbar"
      :aria-valuenow="Math.round(clamped)"
      aria-valuemin="0"
      aria-valuemax="100"
    >
      <div
        class="h-full rounded-full transition-all duration-500 ease-out"
        :class="fillColorClass"
        :style="{ width: clamped + '%' }"
      ></div>
    </div>
    <p v-if="hint" class="mt-1 text-xs text-gray-500">{{ hint }}</p>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  value: { type: Number, default: 0 },
  showLabel: { type: Boolean, default: true },
  label: { type: String, default: 'Progresso' },
  hint: { type: String, default: '' },
  size: { type: String, default: 'md' }, // sm | md | lg
  variant: { type: String, default: 'primary' }, // primary | success | warning
  testId: { type: String, default: 'progress-bar' },
})

const clamped = computed(() => Math.max(0, Math.min(100, props.value || 0)))

const trackClass = computed(() => ({
  sm: 'h-1.5',
  md: 'h-2.5',
  lg: 'h-3.5',
}[props.size] || 'h-2.5'))

const fillColorClass = computed(() => {
  if (props.variant === 'success' || clamped.value >= 100) {
    return 'bg-green-500'
  }
  if (props.variant === 'warning') {
    return 'bg-amber-500'
  }
  return 'bg-primary-600'
})

const valueColorClass = computed(() => {
  if (clamped.value >= 100) return 'text-green-600'
  if (clamped.value > 0) return 'text-primary-600'
  return 'text-gray-500'
})

const labelClass = computed(() => (props.showLabel ? '' : 'sr-only'))
</script>
