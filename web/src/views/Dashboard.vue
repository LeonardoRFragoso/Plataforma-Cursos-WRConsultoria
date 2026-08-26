<template>
  <div class="space-y-7">
    <template v-if="isAdmin">
      <AppPageHeader eyebrow="Visão executiva" title="Dashboard" description="Acompanhe os principais indicadores e acesse rapidamente as operações da plataforma." />

      <div v-if="statsLoading" class="grid grid-cols-2 gap-4 xl:grid-cols-4" data-testid="dashboard-stats-loading">
        <div v-for="i in 4" :key="i" class="h-28 animate-pulse rounded-2xl bg-white/70"></div>
      </div>
      <div v-else-if="statsError" class="rounded-2xl border border-red-200 bg-red-50 p-5 text-sm text-red-700" data-testid="dashboard-stats-error">
        <p class="font-semibold">Não foi possível carregar os indicadores.</p><p class="mt-1">{{ statsError }}</p><button @click="loadStats" class="mt-3 font-semibold underline">Tentar novamente</button>
      </div>
      <section v-else class="grid grid-cols-2 gap-3 sm:gap-4 xl:grid-cols-4">
        <OperationsMetric label="Total de alunos" :value="stats.totalStudents" hint="Base ativa do tenant" icon="users" />
        <OperationsMetric label="Turmas ativas" :value="stats.activeClasses" hint="Em operação" icon="calendar" />
        <OperationsMetric label="Matrículas pendentes" :value="stats.pendingEnrollments" hint="Requerem acompanhamento" icon="clipboard" />
        <OperationsMetric label="Receita do mês" :value="money(stats.monthlyRevenue)" hint="Pagamentos aprovados" icon="chart" />
      </section>

      <section class="grid grid-cols-1 gap-5 xl:grid-cols-5">
        <div class="premium-card relative overflow-hidden p-6 xl:col-span-3 sm:p-7">
          <div class="absolute right-0 top-0 h-52 w-52 translate-x-20 -translate-y-20 rounded-full bg-[var(--brand-primary-soft)]"></div>
          <div class="relative">
            <p class="premium-kicker">Operação integrada</p>
            <h2 class="mt-2 max-w-xl text-2xl font-bold tracking-tight text-slate-900">Tudo que precisa de atenção, sem navegar por dezenas de telas.</h2>
            <p class="mt-2 max-w-2xl text-sm leading-6 text-slate-500">Use a Central Operacional para acompanhar B2B, exceções financeiras e certificados confiáveis em uma única visão.</p>
            <div class="mt-6 flex flex-wrap gap-3">
              <router-link to="/operations" class="inline-flex items-center gap-2 rounded-xl px-4 py-2.5 text-sm font-semibold text-white shadow-md transition hover:-translate-y-px" :style="{ background: 'var(--brand-primary)' }"><NavIcon name="pulse" />Abrir central operacional</router-link>
              <router-link to="/companies" class="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-sm font-semibold text-slate-700 shadow-sm transition hover:bg-slate-50"><NavIcon name="building" />Empresas</router-link>
            </div>
          </div>
        </div>

        <div class="premium-card p-6 xl:col-span-2">
          <div class="flex items-center justify-between"><div><p class="premium-kicker">Atalhos</p><h2 class="mt-1 text-lg font-bold text-slate-900">Gestão diária</h2></div><span class="flex h-10 w-10 items-center justify-center rounded-xl bg-slate-100 text-slate-600"><NavIcon name="layers" /></span></div>
          <div class="mt-5 grid grid-cols-2 gap-2.5">
            <router-link v-for="item in adminQuickLinks" :key="item.to" :to="item.to" class="group flex items-center gap-2.5 rounded-xl border border-slate-100 bg-slate-50/70 px-3 py-3 text-xs font-semibold text-slate-600 transition hover:border-slate-200 hover:bg-white hover:text-slate-900 hover:shadow-sm"><span class="text-[var(--brand-primary)]"><NavIcon :name="item.icon" /></span>{{ item.label }}</router-link>
          </div>
        </div>
      </section>

      <section class="grid grid-cols-1 gap-5 lg:grid-cols-3">
        <router-link to="/operations/corporate" class="premium-card premium-card-hover group p-5"><div class="flex items-start gap-4"><span class="flex h-11 w-11 items-center justify-center rounded-xl bg-blue-50 text-blue-700"><NavIcon name="briefcase" /></span><div><h3 class="font-bold text-slate-900">Corporativo B2B</h3><p class="mt-1 text-sm leading-5 text-slate-500">Empresas, colaboradores, convites, vagas e matrículas em lote.</p><p class="mt-3 text-xs font-bold text-[var(--brand-primary)]">Abrir operação →</p></div></div></router-link>
        <router-link to="/operations/finance" class="premium-card premium-card-hover group p-5"><div class="flex items-start gap-4"><span class="flex h-11 w-11 items-center justify-center rounded-xl bg-amber-50 text-amber-700"><NavIcon name="chart" /></span><div><h3 class="font-bold text-slate-900">Reconciliação financeira</h3><p class="mt-1 text-sm leading-5 text-slate-500">Revisões, chargebacks, refunds e recebíveis corporativos.</p><p class="mt-3 text-xs font-bold text-[var(--brand-primary)]">Ver pendências →</p></div></div></router-link>
        <router-link to="/operations/certificates" class="premium-card premium-card-hover group p-5"><div class="flex items-start gap-4"><span class="flex h-11 w-11 items-center justify-center rounded-xl bg-emerald-50 text-emerald-700"><NavIcon name="shield" /></span><div><h3 class="font-bold text-slate-900">Certificados confiáveis</h3><p class="mt-1 text-sm leading-5 text-slate-500">Validade, revogação, reemissão e histórico auditável.</p><p class="mt-3 text-xs font-bold text-[var(--brand-primary)]">Gerenciar certificados →</p></div></div></router-link>
      </section>
    </template>

    <template v-else-if="isStudent">
      <section class="brand-gradient relative overflow-hidden rounded-[24px] p-6 text-white shadow-xl sm:p-8" data-testid="student-welcome">
        <div class="absolute -right-12 -top-16 h-56 w-56 rounded-full bg-white/10 blur-sm"></div><div class="absolute bottom-0 right-1/4 h-20 w-40 rounded-t-full bg-white/[.04]"></div>
        <div class="relative flex flex-col gap-5 sm:flex-row sm:items-end sm:justify-between">
          <div><p class="text-xs font-semibold uppercase tracking-[.18em] text-white/55">Sua jornada de aprendizagem</p><h1 class="mt-2 text-2xl font-bold tracking-tight sm:text-3xl">Olá, {{ firstName || 'aluno' }} <span aria-hidden="true">👋</span></h1><p class="mt-2 max-w-2xl text-sm leading-6 text-white/75 sm:text-base">{{ welcomeSubtitle }}</p></div>
          <router-link to="/cursos" class="inline-flex w-fit items-center gap-2 rounded-xl bg-white px-4 py-2.5 text-sm font-bold text-slate-900 shadow-lg transition hover:-translate-y-px"><NavIcon name="catalog" />Explorar catálogo</router-link>
        </div>
      </section>

      <section class="grid grid-cols-2 gap-3 sm:gap-4 lg:grid-cols-4">
        <template v-if="loadingEnrollments"><div v-for="i in 4" :key="i" class="h-24 animate-pulse rounded-2xl bg-white/70" /></template>
        <template v-else>
          <StudentMetricCard :value="metrics.total" label="Cursos matriculados" icon="📚" tone="primary" test-id="metric-enrolled" />
          <StudentMetricCard :value="metrics.inProgress" label="Em andamento" icon="▶" tone="primary" test-id="metric-in-progress" />
          <StudentMetricCard :value="metrics.completed" label="Concluídos" icon="✓" tone="success" test-id="metric-completed" />
          <StudentMetricCard :value="metrics.certificates" label="Certificados" icon="🏆" tone="accent" test-id="metric-certificates" />
        </template>
      </section>

      <div v-if="enrollmentsError" class="rounded-2xl border border-red-200 bg-red-50 p-4 text-sm text-red-700" data-testid="dashboard-enrollments-error"><p class="mb-2">{{ enrollmentsError }}</p><button @click="loadMyEnrollments" class="font-semibold underline">Tentar novamente</button></div>

      <div class="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div class="space-y-4 lg:col-span-2">
          <SectionHeader title="Continue aprendendo" description="Retome de onde você parou e avance no seu próximo objetivo."><template #actions><router-link to="/cursos" class="text-sm font-semibold text-[var(--brand-primary)]">Explorar catálogo →</router-link></template></SectionHeader>
          <EmptyState v-if="!loadingEnrollments && myEnrollments.length === 0" icon="📚" title="Você ainda não está matriculado em nenhum curso." description="Explore nosso catálogo e comece sua jornada de aprendizado."><AppLink to="/cursos" class="inline-flex items-center rounded-xl bg-primary-600 px-4 py-2.5 text-sm font-semibold text-white">Explorar catálogo</AppLink></EmptyState>
          <template v-else><template v-if="loadingEnrollments"><div v-for="i in 2" :key="i" class="h-36 animate-pulse rounded-2xl bg-white/70" /></template><template v-else><CourseProgressCard v-for="enrollment in playableEnrollments" :key="enrollment.id" :enrollment="enrollment" :certificate-course-ids="certificateCourseIds" :test-id="'progress-card-' + enrollment.course_id" /><CourseProgressCard v-for="enrollment in pendingEnrollments" :key="enrollment.id" :enrollment="enrollment" :certificate-course-ids="certificateCourseIds" :test-id="'progress-card-pending-' + enrollment.course_id" /></template></template>
        </div>

        <div class="space-y-5">
          <div class="premium-card p-5" data-testid="dashboard-cert-summary"><div class="flex items-center justify-between"><div><p class="premium-kicker">Conquistas</p><h2 class="mt-1 font-bold text-slate-900">Certificados</h2></div><span class="flex h-10 w-10 items-center justify-center rounded-xl bg-amber-50 text-lg">🏆</span></div><template v-if="certificatesLoading"><div class="mt-4 h-20 animate-pulse rounded-xl bg-slate-100" /></template><template v-else-if="myCertificates.length > 0"><div class="mt-4 space-y-2"><div v-for="cert in latestCertificates" :key="cert.id" class="rounded-xl border border-slate-100 bg-slate-50/60 p-3"><p class="truncate text-sm font-semibold text-slate-800">{{ cert.course_name }}</p><p class="mt-1 text-xs text-slate-400">Emitido em {{ formatDate(cert.issued_at) }}</p></div></div><AppLink to="/certificates" class="mt-4 block text-sm font-semibold text-[var(--brand-primary)]">Ver todos →</AppLink></template><EmptyState v-else icon="🏆" title="Nenhum certificado ainda" description="Conclua seus cursos para conquistar certificados." :class_="'py-6'" /></div>
          <StudentProfileCard :user="authStore.user" role="student" />
        </div>
      </div>

      <section v-if="!loadingEnrollments && myEnrollments.length > 0" class="premium-card flex flex-col gap-4 p-5 sm:flex-row sm:items-center sm:justify-between sm:p-6"><div><p class="premium-kicker">Próximo passo</p><h2 class="mt-1 text-lg font-bold text-slate-900">Explore novos treinamentos</h2><p class="mt-1 text-sm text-slate-500">Descubra cursos para continuar sua jornada profissional.</p></div><router-link to="/cursos" class="inline-flex items-center justify-center gap-2 rounded-xl px-4 py-2.5 text-sm font-semibold text-white shadow-md" :style="{ background: 'var(--brand-primary)' }"><NavIcon name="catalog" />Explorar catálogo</router-link></section>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useAuthStore } from '../stores/auth'
import api from '../api/client'
import { fetchMyCertificates } from '../api/certificates'
import AppLink from '../components/AppLink.vue'
import AppPageHeader from '../components/AppPageHeader.vue'
import OperationsMetric from '../components/OperationsMetric.vue'
import StudentMetricCard from '../components/StudentMetricCard.vue'
import CourseProgressCard from '../components/CourseProgressCard.vue'
import StudentProfileCard from '../components/StudentProfileCard.vue'
import SectionHeader from '../components/SectionHeader.vue'
import EmptyState from '../components/EmptyState.vue'
import NavIcon from '../components/NavIcon.vue'

const authStore = useAuthStore()
const isAdmin = computed(() => ['admin','super_admin'].includes(authStore.userRole?.toLowerCase()))
const isStudent = computed(() => authStore.userRole?.toLowerCase() === 'student')
const stats = ref({ totalStudents:0, activeClasses:0, pendingEnrollments:0, monthlyRevenue:0 }); const statsLoading=ref(false); const statsError=ref('')
const myEnrollments=ref([]); const loadingEnrollments=ref(false); const enrollmentsError=ref(''); const myCertificates=ref([]); const certificatesLoading=ref(false)
const adminQuickLinks=[{to:'/courses',label:'Cursos',icon:'catalog'},{to:'/classes',label:'Turmas',icon:'calendar'},{to:'/students',label:'Alunos',icon:'users'},{to:'/enrollments',label:'Matrículas',icon:'clipboard'},{to:'/payments',label:'Pagamentos',icon:'card'},{to:'/certificates',label:'Certificados',icon:'cert'}]
const firstName=computed(()=>{const name=authStore.user?.full_name||'';return name.trim().split(/\s+/)[0]||''})
const playableEnrollments=computed(()=>myEnrollments.value.filter(e=>e.status==='CONFIRMADA'||e.status==='CONCLUIDA')); const pendingEnrollments=computed(()=>myEnrollments.value.filter(e=>e.status==='PENDENTE'||e.status==='CANCELADA')); const certificateCourseIds=computed(()=>new Set(myCertificates.value.map(c=>c.course_id)))
const metrics=computed(()=>{const total=myEnrollments.value.length;const completed=myEnrollments.value.filter(e=>e.status==='CONCLUIDA').length;const blocked=myEnrollments.value.filter(e=>e.status==='PENDENTE'||e.status==='CANCELADA').length;return{total,inProgress:Math.max(0,total-completed-blocked),completed,certificates:myCertificates.value.length}})
const welcomeSubtitle=computed(()=>{const m=metrics.value;if(m.total===0)return'Explore nosso catálogo e comece sua jornada de aprendizado.';if(m.inProgress>0)return`Você tem ${m.inProgress} curso${m.inProgress>1?'s':''} em andamento.`;if(m.completed>0)return`Parabéns! Você concluiu ${m.completed} curso${m.completed>1?'s':''}.`;return'Continue sua jornada de aprendizado.'})
const latestCertificates=computed(()=>myCertificates.value.slice(0,2)); const formatDate=(date)=>new Date(date).toLocaleDateString('pt-BR'); const money=(v)=>Number(v||0).toLocaleString('pt-BR',{style:'currency',currency:'BRL'})
const loadMyEnrollments=async()=>{if(!isStudent.value)return;loadingEnrollments.value=true;enrollmentsError.value='';try{myEnrollments.value=(await api.get('/api/v1/enrollments/me')).data}catch(error){enrollmentsError.value=error.response?.data?.detail||'Não foi possível carregar suas matrículas.'}finally{loadingEnrollments.value=false}}
const loadMyCertificates=async()=>{if(!isStudent.value)return;certificatesLoading.value=true;try{myCertificates.value=(await fetchMyCertificates()).data}catch{myCertificates.value=[]}finally{certificatesLoading.value=false}}
const loadStats=async()=>{if(!isAdmin.value)return;statsLoading.value=true;statsError.value='';try{stats.value=(await api.get('/api/v1/dashboard/stats')).data}catch(error){statsError.value=error.response?.data?.detail||'Não foi possível carregar as estatísticas.'}finally{statsLoading.value=false}}
onMounted(async()=>{await authStore.initializeUser();await Promise.all([loadStats(),loadMyEnrollments(),loadMyCertificates()])})
</script>
