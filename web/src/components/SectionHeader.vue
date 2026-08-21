<template>
  <div class="flex items-end justify-between gap-4 mb-4">
    <div class="min-w-0">
      <h2 class="text-lg sm:text-xl font-semibold text-secondary-900 truncate">
        {{ title }}
      </h2>
      <p v-if="description" class="mt-0.5 text-sm text-gray-500 truncate">{{ description }}</p>
    </div>
    <slot name="actions" />
  </div>
</template>

<script setup>
defineProps({
  title: { type: String, required: true },
  description: { type: String, default: '' },
})
</script>
