<template><div class="rounded-xl border border-gray-200 bg-white p-4 shadow-sm"><p class="text-xs text-gray-500">{{ label }}</p><p class="mt-2 text-2xl font-bold text-gray-900">{{ value ?? 0 }}</p></div></template>
<script setup>defineProps({ label: { type: String, required: true }, value: { type: [String, Number], default: 0 } })</script>
