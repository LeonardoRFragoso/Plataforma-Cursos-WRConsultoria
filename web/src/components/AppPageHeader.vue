<template>
  <div class="mb-7 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between" data-testid="app-page-header">
    <div class="min-w-0">
      <p v-if="eyebrow" class="premium-kicker mb-2">{{ eyebrow }}</p>
      <h1 class="premium-title text-2xl font-bold sm:text-3xl">{{ title }}</h1>
      <p v-if="description" class="mt-2 max-w-3xl text-sm leading-6 text-slate-500">{{ description }}</p>
    </div>
    <div v-if="$slots.actions" class="flex flex-wrap items-center gap-2 sm:shrink-0">
      <slot name="actions" />
    </div>
  </div>
</template>

<script setup>
defineProps({
  title: { type: String, required: true },
  description: { type: String, default: '' },
  eyebrow: { type: String, default: '' },
})
</script>
