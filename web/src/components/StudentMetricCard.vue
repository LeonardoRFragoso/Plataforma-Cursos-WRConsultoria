<template>
  <div class="premium-card premium-card-hover relative overflow-hidden p-4 sm:p-5" :data-testid="testId">
    <div class="absolute -right-8 -top-8 h-24 w-24 rounded-full opacity-60" :class="glowClass"></div>
    <div class="relative flex items-center gap-3.5">
      <div class="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl ring-1 ring-black/[.03]" :class="iconWrapClass"><span class="text-lg" aria-hidden="true">{{ icon }}</span></div>
      <div class="min-w-0"><div class="text-2xl font-bold leading-none tracking-tight text-slate-900">{{ value }}</div><div class="mt-1.5 truncate text-xs font-medium text-slate-500 sm:text-sm">{{ label }}</div></div>
    </div>
  </div>
</template>
<script setup>
import { computed } from 'vue'
const props = defineProps({ value:{type:[Number,String],required:true}, label:{type:String,required:true}, icon:{type:String,default:'📚'}, tone:{type:String,default:'primary'}, testId:{type:String,default:'student-metric-card'} })
const iconWrapClass = computed(() => ({ primary:'bg-primary-50 text-primary-700', success:'bg-emerald-50 text-emerald-700', warning:'bg-amber-50 text-amber-700', accent:'bg-orange-50 text-orange-700' }[props.tone] || 'bg-primary-50 text-primary-700'))
const glowClass = computed(() => ({ primary:'bg-primary-100', success:'bg-emerald-100', warning:'bg-amber-100', accent:'bg-orange-100' }[props.tone] || 'bg-primary-100'))
</script>
