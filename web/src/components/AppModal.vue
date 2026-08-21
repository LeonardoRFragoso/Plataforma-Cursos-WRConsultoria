<template>
  <Teleport to="body">
    <Transition name="modal">
      <div
        v-if="modelValue"
        class="fixed inset-0 z-50 flex items-center justify-center p-4"
        @keydown.esc="handleEscape"
        role="dialog"
        aria-modal="true"
        :aria-labelledby="titleId"
        ref="modalRef"
      >
        <div
          class="absolute inset-0 bg-black bg-opacity-50"
          @click="handleBackdropClick"
          data-testid="modal-backdrop"
        ></div>

        <div
          class="relative bg-white rounded-lg shadow-xl w-full max-h-[90vh] overflow-y-auto"
          :class="sizeClass"
          role="document"
        >
          <!-- Header -->
          <div class="flex items-center justify-between px-6 py-4 border-b border-gray-200">
            <h2 :id="titleId" class="text-lg font-semibold text-secondary-900">
              {{ title }}
            </h2>
            <button
              v-if="closable"
              @click="handleClose"
              class="text-gray-400 hover:text-gray-600 transition-colors"
              :aria-label="'Fechar: ' + title"
              data-testid="modal-close"
            >
              <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
                <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>

          <!-- Body -->
          <div class="px-6 py-4">
            <slot />
          </div>

          <!-- Footer -->
          <div
            v-if="$slots.footer"
            class="px-6 py-4 border-t border-gray-200 flex items-center justify-end gap-2"
          >
            <slot name="footer" />
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
import { computed, nextTick, ref, watch } from 'vue'

const props = defineProps({
  modelValue: {
    type: Boolean,
    default: false,
  },
  title: {
    type: String,
    required: true,
  },
  closable: {
    type: Boolean,
    default: true,
  },
  size: {
    type: String,
    default: 'md',
    validator: (v) => ['sm', 'md', 'lg', 'xl'].includes(v),
  },
  closeOnBackdrop: {
    type: Boolean,
    default: true,
  },
})

const emit = defineEmits(['update:modelValue', 'close'])

const modalRef = ref(null)
const titleId = `modal-title-${Math.random().toString(36).slice(2, 9)}`

const sizeClass = computed(() => {
  const sizes = {
    sm: 'max-w-md',
    md: 'max-w-lg',
    lg: 'max-w-2xl',
    xl: 'max-w-4xl',
  }
  return sizes[props.size] || sizes.md
})

const handleClose = () => {
  if (!props.closable) return
  emit('update:modelValue', false)
  emit('close')
}

const handleBackdropClick = () => {
  if (props.closeOnBackdrop) handleClose()
}

const handleEscape = () => {
  if (props.closable) handleClose()
}

watch(
  () => props.modelValue,
  async (val) => {
    if (val) {
      await nextTick()
      // Focus the modal container for keyboard accessibility
      modalRef.value?.focus()
      // Prevent body scroll
      document.body.style.overflow = 'hidden'
    } else {
      document.body.style.overflow = ''
    }
  }
)
</script>

<style scoped>
.modal-enter-active,
.modal-leave-active {
  transition: opacity 0.2s ease;
}

.modal-enter-from,
.modal-leave-to {
  opacity: 0;
}
</style>
