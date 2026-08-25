<template>
  <div class="space-y-6">
    <div class="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-3"><div><p class="text-sm text-primary-600 font-medium">B2B</p><h1 class="text-3xl font-bold">Operação corporativa</h1><p class="mt-1 text-gray-600">Pipeline comercial e acesso rápido às operações de cada empresa.</p></div><router-link to="/companies" class="text-primary-600 font-medium">Cadastro de empresas →</router-link></div>
    <div v-if="error" class="rounded-lg bg-red-50 p-3 text-red-700">{{ error }}</div>
    <section class="rounded-xl border bg-white overflow-hidden">
      <div class="p-5 border-b"><h2 class="font-semibold text-lg">Solicitações de treinamento</h2></div>
      <div v-if="loading" class="p-8 text-gray-500">Carregando…</div>
      <div v-else-if="!requests.length" class="p-8 text-gray-500">Nenhuma solicitação corporativa.</div>
      <div v-else class="divide-y">
        <div v-for="lead in requests" :key="lead.id" class="p-5 grid lg:grid-cols-[1fr_220px] gap-4">
          <div><div class="flex flex-wrap gap-2 items-center"><h3 class="font-semibold">{{ lead.company_name }}</h3><span class="text-xs px-2 py-1 rounded-full bg-gray-100">{{ lead.status }}</span></div><p class="text-sm text-gray-600 mt-1">{{ lead.contact_name }} · {{ lead.contact_email }}</p><p class="text-sm text-gray-500">{{ lead.course_interest || 'Treinamento não especificado' }} · {{ lead.employee_count || '—' }} colaboradores</p><p v-if="lead.message" class="text-sm mt-2 text-gray-700">{{ lead.message }}</p></div>
          <select :value="lead.status" class="rounded-lg border-gray-300 h-10" @change="changeStatus(lead, $event.target.value)"><option v-for="status in statuses" :key="status">{{ status }}</option></select>
        </div>
      </div>
    </section>
    <section><h2 class="font-semibold text-lg mb-3">Empresas</h2><div class="grid md:grid-cols-2 xl:grid-cols-3 gap-4"><router-link v-for="company in companies" :key="company.id" :to="`/companies/${company.id}/operations`" class="rounded-xl border bg-white p-5 hover:border-primary-300"><p class="font-semibold">{{ company.trade_name || company.legal_name }}</p><p class="text-sm text-gray-500 mt-1">{{ company.cnpj }} · {{ company.status || 'ACTIVE' }}</p><p class="mt-4 text-sm text-primary-600 font-medium">Abrir operação →</p></router-link></div></section>
  </div>
</template>
<script setup>
import { onMounted, ref } from 'vue'
import api from '../api/client'
import { listCorporateRequests, updateCorporateRequest } from '../api/corporate'
const requests = ref([]); const companies = ref([]); const loading = ref(true); const error = ref('')
const statuses = ['NEW','CONTACTED','QUALIFIED','PROPOSAL_SENT','WON','LOST']
async function load(){ loading.value=true; try { const [r,c]=await Promise.all([listCorporateRequests(),api.get('/api/v1/companies/')]); requests.value=r.data; companies.value=c.data } catch(e){ error.value=e.response?.data?.detail||'Erro ao carregar operação corporativa.' } finally { loading.value=false } }
async function changeStatus(lead,status){ try { const {data}=await updateCorporateRequest(lead.id,{status}); Object.assign(lead,data) } catch(e){ error.value=e.response?.data?.detail||'Não foi possível atualizar a solicitação.' } }
onMounted(load)
</script>
