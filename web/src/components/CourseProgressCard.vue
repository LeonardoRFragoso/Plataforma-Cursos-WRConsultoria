<template>
  <div class="premium-card premium-card-hover group overflow-hidden" :data-testid="testId">
    <div class="flex flex-col gap-4 p-4 sm:flex-row sm:p-5">
      <CourseCover
        :course="courseForCover"
        ratio="16/9"
        fit="contain"
        loading="lazy"
        wrapper-class="w-28 shrink-0 overflow-hidden rounded-2xl bg-white shadow-sm sm:w-36"
        img-test-id="progress-card-cover-img"
        fb-test-id="progress-card-cover-fallback"
      />
      <div class="flex min-w-0 flex-1 flex-col">
        <div class="flex items-start justify-between gap-3"><div class="min-w-0"><p class="text-[10px] font-bold uppercase tracking-[.13em] text-[var(--brand-primary)]">{{ enrollment.course_code || 'Treinamento' }}</p><h3 class="mt-1 line-clamp-2 font-bold leading-snug text-slate-900">{{ enrollment.course_name }}</h3></div><StatusBadge v-if="courseState" :status="courseState" :test-id="testId + '-status'" /></div>
        <p v-if="formattedDates" class="mt-1.5 text-xs text-slate-400">{{ formattedDates }}</p>
        <div class="mt-4"><ProgressBar :value="percentage" label="Progresso" :hint="progressHint" :show-label="true" size="md" :test-id="testId + '-progress'" /></div>
        <div class="mt-4 flex flex-wrap gap-2"><router-link :to="learnRoute" class="inline-flex items-center gap-2 rounded-xl px-3.5 py-2 text-xs font-bold transition focus:outline-none focus:ring-4 focus:ring-primary-100" :class="primaryCtaClass" :data-testid="testId + '-cta'"><span aria-hidden="true">{{ primaryCtaIcon }}</span>{{ primaryCtaLabel }}</router-link><router-link v-if="hasCertificate" to="/certificates" class="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-3.5 py-2 text-xs font-bold text-slate-600 transition hover:bg-slate-50" :data-testid="testId + '-cert'"><span aria-hidden="true">🏆</span>Certificado</router-link></div>
      </div>
    </div>
  </div>
</template>
<script setup>
import { computed, ref, watch } from 'vue'; import api from '../api/client'; import CourseCover from './CourseCover.vue'; import ProgressBar from './ProgressBar.vue'; import StatusBadge from './StatusBadge.vue'
const props=defineProps({enrollment:{type:Object,required:true},certificateCourseIds:{type:Set,default:()=>new Set()},testId:{type:String,default:'course-progress-card'}}); const progress=ref(null)
const courseForCover=computed(()=>({id:props.enrollment.course_id,code:props.enrollment.course_code,name:props.enrollment.course_name,category:props.enrollment.course_category,cover_image_url:props.enrollment.cover_image_url,cover_image_alt:props.enrollment.cover_image_alt}))
const percentage=computed(()=>progress.value&&typeof progress.value.percentage==='number'?progress.value.percentage:props.enrollment.status==='CONCLUIDA'?100:0)
const courseState=computed(()=>props.enrollment.status==='CONCLUIDA'?'completed':progress.value&&progress.value.percentage>0?'in_progress':props.enrollment.status==='CONFIRMADA'?'in_progress':props.enrollment.status==='PENDENTE'?'not_started':null)
const hasCertificate=computed(()=>props.certificateCourseIds.has(props.enrollment.course_id)); const canPlay=computed(()=>['CONFIRMADA','CONCLUIDA'].includes(props.enrollment.status)); const learnRoute=computed(()=>canPlay.value?`/courses/${props.enrollment.course_id}/learn`:'/cursos')
const primaryCtaLabel=computed(()=>!canPlay.value?'Ver catálogo':courseState.value==='completed'?'Revisar curso':courseState.value==='in_progress'?'Continuar curso':'Começar curso'); const primaryCtaIcon=computed(()=>!canPlay.value?'→':courseState.value==='completed'?'↺':'▶'); const primaryCtaClass=computed(()=>canPlay.value?'text-white shadow-sm':'border border-slate-200 bg-white text-slate-700 hover:bg-slate-50')
const progressHint=computed(()=>{if(progress.value&&typeof progress.value.required_lessons==='number'){const c=progress.value.completed_required||0,r=progress.value.required_lessons||0;if(r>0)return`${c} de ${r} aulas obrigatórias`}if(props.enrollment.status==='CONCLUIDA')return'Curso concluído';if(props.enrollment.status==='PENDENTE')return'Aguardando confirmação da matrícula';return''})
const formattedDates=computed(()=>{const s=props.enrollment.start_date,e=props.enrollment.end_date;if(!s||!e)return'';const months=['jan','fev','mar','abr','mai','jun','jul','ago','set','out','nov','dez'],sd=new Date(s),ed=new Date(e);return`${sd.getDate()} ${months[sd.getMonth()]} — ${ed.getDate()} ${months[ed.getMonth()]} ${ed.getFullYear()}`})
const loadProgress=async()=>{if(!canPlay.value)return;try{progress.value=(await api.get(`/api/v1/lessons/courses/${props.enrollment.course_id}/my-progress`)).data}catch{progress.value=null}}
watch(()=>props.enrollment?.course_id,()=>loadProgress(),{immediate:true})
</script>
<style scoped>a.text-white{background:var(--brand-primary)}a.text-white:hover{background:var(--brand-primary-hover)}</style>
