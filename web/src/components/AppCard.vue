<template>
  <div
    :class="[
      'bg-white rounded-lg border border-gray-200 shadow-md p-6',
      hoverable && 'hover:shadow-lg transition-shadow cursor-pointer'
    ]"
  >
    <div v-if="$slots.header" class="mb-4">
      <slot name="header" />
    </div>
    
    <slot />
    
    <div v-if="$slots.footer" class="mt-4 pt-4 border-t border-gray-200">
      <slot name="footer" />
    </div>
  </div>
</template>

<script setup>
defineProps({
  hoverable: {
    type: Boolean,
    default: false
  }
})
</script>
