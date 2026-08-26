<template>
  <button
    :type="type"
    :disabled="disabled"
    :class="[
      'inline-flex items-center justify-center gap-2 rounded-xl font-semibold shadow-sm transition-all duration-150 focus-visible:outline-none disabled:pointer-events-none',
      variantClasses,
      sizeClasses,
      disabled && 'cursor-not-allowed opacity-50'
    ]"
  >
    <slot />
  </button>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  type: { type: String, default: 'button', validator: (value) => ['button', 'submit', 'reset'].includes(value) },
  variant: { type: String, default: 'primary', validator: (value) => ['primary', 'secondary', 'outline', 'danger', 'ghost'].includes(value) },
  size: { type: String, default: 'md', validator: (value) => ['sm', 'md', 'lg'].includes(value) },
  disabled: { type: Boolean, default: false },
})

const variantClasses = computed(() => ({
  primary: 'text-white hover:-translate-y-px hover:shadow-md active:translate-y-0',
  secondary: 'border border-slate-200 bg-white text-slate-700 hover:border-slate-300 hover:bg-slate-50',
  outline: 'border text-primary hover:bg-primary-50',
  danger: 'bg-red-600 text-white hover:bg-red-700 hover:-translate-y-px',
  ghost: 'bg-transparent text-slate-600 shadow-none hover:bg-slate-100 hover:text-slate-900',
}[props.variant] || '') )

const sizeClasses = computed(() => ({
  sm: 'min-h-9 px-3.5 py-2 text-xs',
  md: 'min-h-10 px-4 py-2.5 text-sm',
  lg: 'min-h-12 px-5 py-3 text-base',
}[props.size] || '') )
</script>

<style scoped>
button.text-white:not(.bg-red-600) { background: var(--brand-primary); }
button.text-white:not(.bg-red-600):hover { background: var(--brand-primary-hover); }
button.text-primary { border-color: color-mix(in srgb, var(--brand-primary) 55%, white); color: var(--brand-primary); }
button.text-primary:hover { background: var(--brand-primary-soft); }
</style>
