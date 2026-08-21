<template>
  <div
    class="mb-8 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between"
    data-testid="app-page-header"
  >
    <div class="min-w-0">
      <h1 class="text-2xl font-bold text-secondary-900 truncate">{{ title }}</h1>
      <p v-if="description" class="mt-1 text-sm text-gray-600">{{ description }}</p>
    </div>
    <div v-if="$slots.actions" class="flex flex-wrap gap-2 sm:shrink-0">
      <slot name="actions" />
    </div>
  </div>
</template>

<script setup>
/**
 * AppPageHeader — reusable authenticated page header.
 *
 * Standardizes title, description and primary actions across all management
 * screens so the workspace hierarchy stays coherent.
 */
defineProps({
  title: { type: String, required: true },
  description: { type: String, default: '' },
})
</script>
