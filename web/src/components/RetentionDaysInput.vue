<template>
  <label class="block">
    <span class="text-xs font-bold text-slate-600">{{ label }}</span>
    <input
      type="number"
      inputmode="numeric"
      min="1"
      step="1"
      :value="modelValue"
      :disabled="disabled"
      :placeholder="disabled ? '—' : 'dias'"
      class="mt-1 w-full text-sm"
      data-testid="retention-days-input"
      @input="$emit('update:modelValue', $event.target.value === '' ? null : Number($event.target.value))"
    />
  </label>
</template>

<script setup>
defineProps({
  modelValue: { type: [Number, String, null], default: null },
  label: { type: String, required: true },
  disabled: { type: Boolean, default: false },
})
defineEmits(['update:modelValue'])
</script>
