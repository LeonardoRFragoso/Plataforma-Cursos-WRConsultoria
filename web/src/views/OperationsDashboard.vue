<template>
  <div class="space-y-8">
    <div>
      <p class="text-sm font-medium text-primary-600">Operações</p>
      <h1 class="text-3xl font-bold text-gray-900">Central operacional</h1>
      <p class="mt-2 text-gray-600">Pendências comerciais, financeiras e de certificação em uma única visão.</p>
    </div>

    <div v-if="loading" class="py-16 text-center text-gray-500">Carregando indicadores…</div>
    <div v-else-if="error" class="rounded-xl bg-red-50 border border-red-200 p-4 text-red-700">{{ error }}</div>
    <template v-else>
      <section class="grid grid-cols-2 xl:grid-cols-6 gap-4">
        <Metric label="Empresas" :value="data.summary.totalCompanies" />
        <Metric label="Matrículas corporativas" :value="data.summary.corporateEnrollments" />
        <Metric label="Revisões financeiras" :value="data.summary.openFinancialReviews" />
        <Metric label="Leads B2B novos" :value="data.summary.newCorporateRequests" />
        <Metric label="Certificados a vencer" :value="data.summary.expiringCertificates30d" />
        <Metric label="Receita líquida/mês" :value="money(data.summary.monthlyNetRevenue)" />
      </section>

      <section class="grid grid-cols-1 lg:grid-cols-3 gap-5">
        <router-link to="/operations/corporate" class="rounded-xl border bg-white p-5 hover:border-primary-300"><h2 class="font-semibold text-lg">Operação corporativa</h2><p class="mt-1 text-sm text-gray-600">Leads, empresas, colaboradores, vagas e matrículas em lote.</p></router-link>
        <router-link to="/operations/finance" class="rounded-xl border bg-white p-5 hover:border-primary-300"><h2 class="font-semibold text-lg">Reconciliação financeira</h2><p class="mt-1 text-sm text-gray-600">Chargebacks, refunds, revisão manual e recebíveis B2B.</p></router-link>
        <router-link to="/operations/certificates" class="rounded-xl border bg-white p-5 hover:border-primary-300"><h2 class="font-semibold text-lg">Certificados confiáveis</h2><p class="mt-1 text-sm text-gray-600">Validade, revogação, reemissão e histórico.</p></router-link>
      </section>

      <section class="grid grid-cols-1 xl:grid-cols-3 gap-5">
        <Queue title="Revisões financeiras" :items="data.queues.financialReviews" empty="Nenhuma revisão aberta">
          <template #default="{ item }"><div class="flex justify-between gap-3"><div><p class="font-medium">{{ item.reason }}</p><p class="text-xs text-gray-500">{{ item.provider }} · {{ item.priority }}</p></div><span class="font-semibold">{{ money(item.amount) }}</span></div></template>
        </Queue>
        <Queue title="Solicitações corporativas" :items="data.queues.corporateRequests" empty="Nenhuma solicitação pendente">
          <template #default="{ item }"><p class="font-medium">{{ item.company_name }}</p><p class="text-xs text-gray-500">{{ item.contact_name }} · {{ item.employee_count || '—' }} colaboradores</p></template>
        </Queue>
        <Queue title="Certificados a vencer em 30 dias" :items="data.queues.expiringCertificates" empty="Nenhum vencimento próximo">
          <template #default="{ item }"><p class="font-medium">{{ item.certificate_number }}</p><p class="text-xs text-gray-500">Vencimento: {{ date(item.expires_at) }} · versão {{ item.version }}</p></template>
        </Queue>
      </section>
    </template>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import api from '../api/client'
import Metric from '../components/OperationsMetric.vue'
import Queue from '../components/OperationsQueue.vue'

const loading = ref(true)
const error = ref('')
const data = ref({ summary: {}, queues: { financialReviews: [], corporateRequests: [], expiringCertificates: [] } })
const money = (value) => Number(value || 0).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })
const date = (value) => value ? new Date(value).toLocaleDateString('pt-BR') : '—'

onMounted(async () => {
  try { data.value = (await api.get('/api/v1/dashboard/operations')).data }
  catch (err) { error.value = err.response?.data?.detail || 'Não foi possível carregar a central operacional.' }
  finally { loading.value = false }
})
</script>
