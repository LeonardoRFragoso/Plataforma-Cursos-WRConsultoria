<template>
  <div
    class="text-center py-12 px-4"
    :class="class_"
    data-testid="loading-state"
    role="status"
    aria-live="polite"
  >
    <svg class="animate-spin w-8 h-8 mx-auto text-primary-600 mb-3" fill="none" viewBox="0 0 24 24">
      <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
      <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
    </svg>
    <p class="text-sm text-gray-600">{{ message }}</p>
  </div>
</template>

<script setup>
defineProps({
  message: {
    type: String,
    default: 'Carregando...',
  },
  class_: {
    type: String,
    default: '',
  },
})
</script>
