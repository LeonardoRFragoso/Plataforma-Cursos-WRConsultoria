<template>
  <span
    class="inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium"
    :class="badgeClass"
    :data-testid="testId"
  >
    <span v-if="dot" class="w-1.5 h-1.5 rounded-full" :class="dotClass"></span>
    {{ label }}
  </span>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  status: { type: String, required: true },
  // 'enrollment' (PENDENTE/CONFIRMADA/CONCLUIDA/CANCELADA)
  // 'course'   (not_started/in_progress/completed)
  // 'generic'  (any lowercase token mapped via customMap)
  customMap: { type: Object, default: () => ({}) },
  testId: { type: String, default: 'status-badge' },
})

const PATTERNS = {
  // Enrollment statuses (backend uppercase)
  PENDENTE: { label: 'Pendente', class: 'bg-amber-100 text-amber-800', dot: 'bg-amber-500' },
  CONFIRMADA: { label: 'Confirmado', class: 'bg-blue-100 text-blue-800', dot: 'bg-blue-500' },
  CONCLUIDA: { label: 'Concluído', class: 'bg-green-100 text-green-800', dot: 'bg-green-500' },
  CANCELADA: { label: 'Cancelado', class: 'bg-red-100 text-red-800', dot: 'bg-red-500' },
  // Course progress states (frontend lowercase)
  not_started: { label: 'Não iniciado', class: 'bg-gray-100 text-gray-700', dot: 'bg-gray-400' },
  in_progress: { label: 'Em andamento', class: 'bg-blue-100 text-blue-800', dot: 'bg-blue-500' },
  completed: { label: 'Concluído', class: 'bg-green-100 text-green-800', dot: 'bg-green-500' },
}

const resolved = computed(() => {
  const key = props.status
  if (props.customMap[key]) return props.customMap[key]
  return PATTERNS[key] || { label: key, class: 'bg-gray-100 text-gray-700', dot: 'bg-gray-400' }
})

const label = computed(() => resolved.value.label)
const badgeClass = computed(() => resolved.value.class)
const dotClass = computed(() => resolved.value.dot)
const dot = computed(() => !!resolved.value.dot)
</script>
