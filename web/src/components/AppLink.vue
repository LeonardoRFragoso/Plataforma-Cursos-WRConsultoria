<template>
  <router-link
    v-if="to"
    :to="to"
    :class="[
      'transition-colors font-medium',
      variantClasses,
      underline && 'underline'
    ]"
  >
    <slot />
  </router-link>
  <a
    v-else
    :href="href"
    :target="target"
    :rel="target === '_blank' ? 'noopener noreferrer' : ''"
    :class="[
      'transition-colors font-medium',
      variantClasses,
      underline && 'underline'
    ]"
  >
    <slot />
  </a>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  to: {
    type: String,
    default: ''
  },
  href: {
    type: String,
    default: ''
  },
  variant: {
    type: String,
    default: 'primary',
    validator: (value) => ['primary', 'secondary', 'danger'].includes(value)
  },
  target: {
    type: String,
    default: '_self'
  },
  underline: {
    type: Boolean,
    default: true
  }
})

const variantClasses = computed(() => {
  const variants = {
    primary: 'text-primary-600 hover:text-primary-700',
    secondary: 'text-gray-600 hover:text-gray-800',
    danger: 'text-red-600 hover:text-red-700'
  }
  return variants[props.variant] || variants.primary
})
</script>
