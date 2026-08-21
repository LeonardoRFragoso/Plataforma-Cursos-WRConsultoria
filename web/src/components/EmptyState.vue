<template>
  <div
    class="text-center py-12 px-4"
    :class="class_"
    data-testid="empty-state"
  >
    <div v-if="icon" class="mb-3">
      <span v-if="isEmoji" class="text-4xl" aria-hidden="true">{{ icon }}</span>
      <svg v-else class="w-12 h-12 mx-auto text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.5">
        <path stroke-linecap="round" stroke-linejoin="round" :d="icon" />
      </svg>
    </div>
    <h3 v-if="title" class="text-lg font-medium text-gray-900 mb-1">{{ title }}</h3>
    <p v-if="description" class="text-sm text-gray-500 max-w-sm mx-auto">{{ description }}</p>
    <div v-if="$slots.default" class="mt-4">
      <slot />
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  title: {
    type: String,
    required: true,
  },
  description: {
    type: String,
    default: '',
  },
  icon: {
    type: String,
    default: 'M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 01-.707.293h-3.172a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 006.586 13H4',
  },
  class_: {
    type: String,
    default: '',
  },
})

// Detect emoji icons (short, non-path strings) vs SVG path data.
const isEmoji = computed(() => {
  const v = props.icon || ''
  if (!v) return false
  // SVG path data starts with M/m/L/l/C/c etc. and contains numbers
  return !/^[MmLlCcHhVvZzAa]/.test(v) && v.length <= 4
})
</script>
