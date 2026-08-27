<template>
  <div class="flex items-center justify-between gap-3 rounded-xl border border-slate-100 bg-white px-3 py-2">
    <span class="min-w-0 truncate text-sm text-slate-600">{{ label }}</span>
    <span class="shrink-0 rounded-full bg-slate-100 px-2.5 py-1 text-xs font-bold text-slate-700">{{ value ?? 0 }}</span>
  </div>
</template>

<script setup>
defineProps({
  label: { type: String, required: true },
  value: { type: [String, Number], default: 0 },
})
</script>
