<template>
  <div
    :class="[
      'premium-card p-5 sm:p-6',
      hoverable && 'premium-card-hover cursor-pointer'
    ]"
  >
    <div v-if="$slots.header" class="mb-5">
      <slot name="header" />
    </div>
    <slot />
    <div v-if="$slots.footer" class="mt-5 border-t border-slate-100 pt-4">
      <slot name="footer" />
    </div>
  </div>
</template>

<script setup>
defineProps({
  hoverable: { type: Boolean, default: false },
})
</script>
