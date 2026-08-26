<template>
  <div class="premium-card premium-card-hover relative overflow-hidden p-4 sm:p-5">
    <div class="absolute -right-5 -top-5 h-20 w-20 rounded-full bg-[var(--brand-primary-soft)]"></div>
    <div class="relative flex items-start justify-between gap-3">
      <div class="min-w-0"><p class="text-xs font-semibold text-slate-500">{{ label }}</p><p class="mt-2 truncate text-2xl font-bold tracking-tight text-slate-900">{{ value ?? 0 }}</p><p v-if="hint" class="mt-1 text-[11px] text-slate-400">{{ hint }}</p></div>
      <div v-if="icon" class="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-[var(--brand-primary-soft)] text-[var(--brand-primary)]"><NavIcon :name="icon" /></div>
    </div>
  </div>
</template>
<script setup>
import NavIcon from './NavIcon.vue'
defineProps({ label:{type:String,required:true}, value:{type:[String,Number],default:0}, hint:{type:String,default:''}, icon:{type:String,default:''} })
</script>
