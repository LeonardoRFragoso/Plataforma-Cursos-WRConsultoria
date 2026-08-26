<template>
  <div class="w-full">
    <label v-if="label" class="mb-2 block text-sm font-semibold text-slate-700">
      {{ label }}
      <span v-if="required" class="text-red-500">*</span>
    </label>
    <input
      :type="type"
      :value="modelValue"
      :placeholder="placeholder"
      :required="required"
      :disabled="disabled"
      :step="step"
      @input="handleInput"
      :class="[
        'w-full rounded-xl border bg-white px-4 py-2.5 text-sm text-slate-900 shadow-sm outline-none transition',
        error ? 'border-red-300 focus:border-red-400 focus:ring-4 focus:ring-red-50' : 'border-slate-200 focus:border-primary-500 focus:ring-4 focus:ring-primary-50',
        disabled && 'cursor-not-allowed bg-slate-50 opacity-60'
      ]"
    />
    <p v-if="error" class="mt-1.5 text-xs font-medium text-red-600">{{ error }}</p>
  </div>
</template>

<script setup>
defineProps({
  modelValue: { type: [String, Number], default: '' },
  type: { type: String, default: 'text' },
  label: { type: String, default: '' },
  placeholder: { type: String, default: '' },
  required: { type: Boolean, default: false },
  disabled: { type: Boolean, default: false },
  error: { type: String, default: '' },
  step: { type: String, default: '1' },
})
const emit = defineEmits(['update:modelValue'])
const handleInput = (event) => emit('update:modelValue', event.target.value)
</script>
