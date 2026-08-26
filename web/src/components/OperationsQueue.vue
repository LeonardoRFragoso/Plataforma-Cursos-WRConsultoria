<template>
  <div class="premium-card p-5 sm:p-6">
    <div class="flex items-center justify-between gap-3"><div><p class="premium-kicker">Fila</p><h2 class="mt-1 font-bold tracking-tight text-slate-900">{{ title }}</h2></div><span class="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-bold text-slate-500">{{ items.length }}</span></div>
    <div v-if="!items.length" class="mt-4 rounded-xl border border-dashed border-slate-200 bg-slate-50/70 px-4 py-8 text-center text-sm text-slate-400">{{ empty }}</div>
    <div v-else class="mt-4 divide-y divide-slate-100"><div v-for="item in items" :key="item.id" class="py-3.5 first:pt-0 last:pb-0"><slot :item="item" /></div></div>
  </div>
</template>
<script setup>defineProps({ title:{type:String,required:true}, items:{type:Array,default:()=>[]}, empty:{type:String,default:'Sem pendências'} })</script>
