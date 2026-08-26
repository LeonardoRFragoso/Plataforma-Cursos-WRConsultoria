<template>
  <div class="space-y-7">
    <div class="brand-gradient relative overflow-hidden rounded-[24px] p-6 text-white shadow-xl sm:p-8">
      <div class="absolute -right-16 -top-20 h-64 w-64 rounded-full bg-white/10"></div>
      <div class="relative flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between"><div><p class="text-xs font-bold uppercase tracking-[.18em] text-white/55">Command center</p><h1 class="mt-2 text-2xl font-bold tracking-tight sm:text-3xl">Central operacional</h1><p class="mt-2 max-w-2xl text-sm leading-6 text-white/75">Pendências comerciais, financeiras e de certificação reunidas para uma operação mais rápida e previsível.</p></div><div class="rounded-2xl border border-white/10 bg-white/10 px-4 py-3 text-xs text-white/70 backdrop-blur"><span class="font-bold text-white">Priorize exceções.</span><br>O que está saudável continua automático.</div></div>
    </div>
    <div v-if="loading" class="grid grid-cols-2 gap-4 xl:grid-cols-6"><div v-for="i in 6" :key="i" class="h-28 animate-pulse rounded-2xl bg-white/70"></div></div>
    <div v-else-if="error" class="rounded-2xl border border-red-200 bg-red-50 p-5 text-red-700">{{ error }}</div>
    <template v-else>
      <section class="grid grid-cols-2 gap-3 sm:gap-4 xl:grid-cols-6">
        <Metric label="Empresas" :value="data.summary.totalCompanies" icon="building" />
        <Metric label="Matrículas B2B" :value="data.summary.corporateEnrollments" icon="clipboard" />
        <Metric label="Revisões financeiras" :value="data.summary.openFinancialReviews" icon="chart" />
        <Metric label="Leads B2B novos" :value="data.summary.newCorporateRequests" icon="briefcase" />
        <Metric label="Certificados a vencer" :value="data.summary.expiringCertificates30d" icon="shield" />
        <Metric label="Receita líquida/mês" :value="money(data.summary.monthlyNetRevenue)" icon="card" />
      </section>
      <section class="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <router-link v-for="area in areas" :key="area.to" :to="area.to" class="premium-card premium-card-hover group p-5"><div class="flex items-start gap-4"><span class="flex h-11 w-11 items-center justify-center rounded-xl" :class="area.tone"><NavIcon :name="area.icon" /></span><div class="min-w-0"><h2 class="font-bold text-slate-900">{{ area.title }}</h2><p class="mt-1 text-sm leading-5 text-slate-500">{{ area.description }}</p><p class="mt-3 text-xs font-bold text-[var(--brand-primary)]">Acessar →</p></div></div></router-link>
      </section>
      <section class="grid grid-cols-1 gap-5 xl:grid-cols-3">
        <Queue title="Revisões financeiras" :items="data.queues.financialReviews" empty="Nenhuma revisão aberta"><template #default="{ item }"><div class="flex justify-between gap-3"><div class="min-w-0"><p class="truncate text-sm font-semibold text-slate-800">{{ item.reason }}</p><p class="mt-1 text-xs text-slate-400">{{ item.provider }} · {{ item.priority }}</p></div><span class="shrink-0 text-sm font-bold text-slate-700">{{ money(item.amount) }}</span></div></template></Queue>
        <Queue title="Solicitações corporativas" :items="data.queues.corporateRequests" empty="Nenhuma solicitação pendente"><template #default="{ item }"><p class="text-sm font-semibold text-slate-800">{{ item.company_name }}</p><p class="mt-1 text-xs text-slate-400">{{ item.contact_name }} · {{ item.employee_count || '—' }} colaboradores</p></template></Queue>
        <Queue title="Certificados a vencer em 30 dias" :items="data.queues.expiringCertificates" empty="Nenhum vencimento próximo"><template #default="{ item }"><p class="text-sm font-semibold text-slate-800">{{ item.certificate_number }}</p><p class="mt-1 text-xs text-slate-400">Vencimento: {{ date(item.expires_at) }} · versão {{ item.version }}</p></template></Queue>
      </section>
    </template>
  </div>
</template>
<script setup>
import { onMounted, ref } from 'vue'; import api from '../api/client'; import Metric from '../components/OperationsMetric.vue'; import Queue from '../components/OperationsQueue.vue'; import NavIcon from '../components/NavIcon.vue'
const loading=ref(true); const error=ref(''); const data=ref({summary:{},queues:{financialReviews:[],corporateRequests:[],expiringCertificates:[]}})
const areas=[{to:'/operations/corporate',title:'Operação corporativa',description:'Leads, empresas, colaboradores, vagas e matrículas em lote.',icon:'briefcase',tone:'bg-blue-50 text-blue-700'},{to:'/operations/finance',title:'Reconciliação financeira',description:'Chargebacks, refunds, revisão manual e recebíveis B2B.',icon:'chart',tone:'bg-amber-50 text-amber-700'},{to:'/operations/certificates',title:'Certificados confiáveis',description:'Validade, revogação, reemissão e histórico auditável.',icon:'shield',tone:'bg-emerald-50 text-emerald-700'}]
const money=(v)=>Number(v||0).toLocaleString('pt-BR',{style:'currency',currency:'BRL'}); const date=(v)=>v?new Date(v).toLocaleDateString('pt-BR'):'—'
onMounted(async()=>{try{data.value=(await api.get('/api/v1/dashboard/operations')).data}catch(err){error.value=err.response?.data?.detail||'Não foi possível carregar a central operacional.'}finally{loading.value=false}})
</script>
