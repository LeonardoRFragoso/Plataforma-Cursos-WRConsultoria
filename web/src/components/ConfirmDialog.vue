<template>
  <AppModal
    :model-value="modelValue"
    @update:model-value="emit('update:modelValue', $event)"
    :title="title"
    :closable="!loading"
    :close-on-backdrop="!loading"
    size="sm"
    @close="emit('close')"
  >
    <p class="text-sm text-gray-600">
      {{ message }}
    </p>

    <template #footer>
      <button
        type="button"
        @click="handleCancel"
        :disabled="loading"
        class="px-4 py-2 rounded-md text-sm font-medium text-gray-700 bg-gray-200 hover:bg-gray-300 transition-colors disabled:opacity-50"
        data-testid="confirm-cancel"
      >
        {{ cancelText }}
      </button>
      <button
        type="button"
        @click="handleConfirm"
        :disabled="loading"
        :class="[
          'px-4 py-2 rounded-md text-sm font-medium text-white transition-colors disabled:opacity-50',
          danger ? 'bg-red-600 hover:bg-red-700' : 'bg-primary-600 hover:bg-primary-700'
        ]"
        data-testid="confirm-ok"
      >
        {{ loading ? 'Processando...' : confirmText }}
      </button>
    </template>
  </AppModal>
</template>

<script setup>
import AppModal from './AppModal.vue'

const props = defineProps({
  modelValue: {
    type: Boolean,
    default: false,
  },
  title: {
    type: String,
    required: true,
  },
  message: {
    type: String,
    required: true,
  },
  confirmText: {
    type: String,
    default: 'Confirmar',
  },
  cancelText: {
    type: String,
    default: 'Cancelar',
  },
  danger: {
    type: Boolean,
    default: false,
  },
  loading: {
    type: Boolean,
    default: false,
  },
})

const emit = defineEmits(['update:modelValue', 'confirm', 'cancel', 'close'])

const handleConfirm = () => {
  emit('confirm')
}

const handleCancel = () => {
  if (props.loading) return
  emit('update:modelValue', false)
  emit('cancel')
  emit('close')
}
</script>
