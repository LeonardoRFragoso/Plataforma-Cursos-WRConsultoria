<template>
  <div class="min-h-screen bg-gray-50">
    <AppNavbar />
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <h1 class="text-2xl font-bold text-secondary-900 mb-6">SUPER_ADMIN — Painel SaaS</h1>

      <div v-if="error" class="mb-4 rounded-md bg-red-50 p-4 text-sm text-red-700">{{ error }}</div>

      <!-- Tabs -->
      <div class="flex space-x-1 mb-6 border-b border-gray-200">
        <button
          v-for="tab in tabs"
          :key="tab"
          @click="activeTab = tab"
          :class="[
            'px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors',
            activeTab === tab
              ? 'border-primary-600 text-primary-600'
              : 'border-transparent text-gray-500 hover:text-gray-700',
          ]"
        >
          {{ tab }}
        </button>
      </div>

      <!-- Partners -->
      <div v-if="activeTab === 'Parceiros'" class="space-y-4">
        <div class="bg-white rounded-lg shadow border border-gray-200 overflow-hidden">
          <table class="min-w-full divide-y divide-gray-200">
            <thead class="bg-gray-50">
              <tr>
                <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Empresa</th>
                <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Contato</th>
                <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
                <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Ação</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-gray-200">
              <tr v-for="lead in partnerLeads" :key="lead.id">
                <td class="px-4 py-3 text-sm text-gray-900">{{ lead.company_name }}</td>
                <td class="px-4 py-3 text-sm text-gray-500">{{ lead.contact_name }} / {{ lead.contact_email }}</td>
                <td class="px-4 py-3 text-sm">
                  <span :class="lead.status === 'APPROVED' ? 'text-green-600' : 'text-yellow-600'">{{ lead.status }}</span>
                </td>
                <td class="px-4 py-3 text-sm">
                  <button
                    v-if="lead.status === 'NEW'"
                    @click="handleApprove(lead.id)"
                    class="text-primary-600 hover:text-primary-700 font-medium"
                  >
                    Aprovar
                  </button>
                  <span v-if="lead.status === 'APPROVED'" class="text-gray-400">Aprovado</span>
                </td>
              </tr>
              <tr v-if="partnerLeads.length === 0">
                <td colspan="4" class="px-4 py-6 text-center text-sm text-gray-400">Nenhum lead</td>
              </tr>
            </tbody>
          </table>
        </div>
        <div v-if="approvalResult" class="bg-green-50 border border-green-200 rounded-md p-4">
          <p class="text-sm font-medium text-green-800">Parceiro aprovado! (DEMO MODE)</p>
          <p class="text-xs text-green-700 mt-1">Tenant ID: {{ approvalResult.tenant_id }}</p>
          <p class="text-xs text-green-700">Admin User ID: {{ approvalResult.admin_user_id }}</p>
          <p class="text-xs text-green-700">Activation Token: {{ approvalResult.activation_token }}</p>
        </div>
      </div>

      <!-- Tenants -->
      <div v-if="activeTab === 'Tenants'" class="bg-white rounded-lg shadow border border-gray-200 overflow-hidden">
        <table class="min-w-full divide-y divide-gray-200">
          <thead class="bg-gray-50">
            <tr>
              <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Nome</th>
              <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Slug</th>
              <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
              <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Domínio</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-gray-200">
            <tr v-for="t in tenants" :key="t.id">
              <td class="px-4 py-3 text-sm text-gray-900">{{ t.name }}</td>
              <td class="px-4 py-3 text-sm text-gray-500">{{ t.slug }}</td>
              <td class="px-4 py-3 text-sm">{{ t.status }}</td>
              <td class="px-4 py-3 text-sm text-gray-500">{{ t.custom_domain || '—' }}</td>
            </tr>
            <tr v-if="tenants.length === 0">
              <td colspan="4" class="px-4 py-6 text-center text-sm text-gray-400">Nenhum tenant</td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- Plans -->
      <div v-if="activeTab === 'Planos'" class="space-y-4">
        <div class="bg-white rounded-lg shadow border border-gray-200 p-4">
          <h3 class="text-sm font-medium text-gray-700 mb-3">Criar Plano</h3>
          <div class="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <input v-model="newPlan.name" placeholder="Nome" class="rounded-md border-gray-300 border px-3 py-2 text-sm" />
            <input v-model.number="newPlan.price" type="number" placeholder="Preço" class="rounded-md border-gray-300 border px-3 py-2 text-sm" />
            <select v-model="newPlan.billing_cycle" class="rounded-md border-gray-300 border px-3 py-2 text-sm">
              <option value="MONTHLY">Mensal</option>
              <option value="YEARLY">Anual</option>
            </select>
          </div>
          <button @click="handleCreatePlan" class="mt-3 bg-primary-600 text-white px-4 py-2 rounded-md text-sm font-medium hover:bg-primary-700">Criar</button>
        </div>
        <div class="bg-white rounded-lg shadow border border-gray-200 overflow-hidden">
          <table class="min-w-full divide-y divide-gray-200">
            <thead class="bg-gray-50">
              <tr>
                <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Nome</th>
                <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Preço</th>
                <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Ciclo</th>
                <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Ativo</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-gray-200">
              <tr v-for="p in plans" :key="p.id">
                <td class="px-4 py-3 text-sm text-gray-900">{{ p.name }}</td>
                <td class="px-4 py-3 text-sm text-gray-500">R$ {{ p.price }}</td>
                <td class="px-4 py-3 text-sm text-gray-500">{{ p.billing_cycle }}</td>
                <td class="px-4 py-3 text-sm">{{ p.is_active ? 'Sim' : 'Não' }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Subscriptions -->
      <div v-if="activeTab === 'Assinaturas'" class="bg-white rounded-lg shadow border border-gray-200 overflow-hidden">
        <table class="min-w-full divide-y divide-gray-200">
          <thead class="bg-gray-50">
            <tr>
              <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">ID</th>
              <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Tenant</th>
              <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
              <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Ações</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-gray-200">
            <tr v-for="s in subscriptions" :key="s.id">
              <td class="px-4 py-3 text-xs text-gray-400 font-mono">{{ s.id.slice(0, 8) }}</td>
              <td class="px-4 py-3 text-xs text-gray-500 font-mono">{{ s.tenant_id.slice(0, 8) }}</td>
              <td class="px-4 py-3 text-sm">
                <span :class="statusClass(s.status)">{{ s.status }}</span>
              </td>
              <td class="px-4 py-3 text-sm space-x-2">
                <button v-if="s.status !== 'ACTIVE'" @click="handleActivate(s.id)" class="text-green-600 hover:text-green-700 font-medium">Ativar</button>
                <button v-if="s.status === 'ACTIVE'" @click="handleSuspend(s.id)" class="text-yellow-600 hover:text-yellow-700 font-medium">Suspender</button>
                <button v-if="s.status === 'SUSPENDED'" @click="handleActivate(s.id)" class="text-green-600 hover:text-green-700 font-medium">Reativar</button>
                <button @click="handleRenew(s.id)" class="text-blue-600 hover:text-blue-700 font-medium">Renovar</button>
              </td>
            </tr>
            <tr v-if="subscriptions.length === 0">
              <td colspan="4" class="px-4 py-6 text-center text-sm text-gray-400">Nenhuma assinatura</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import AppNavbar from '../components/AppNavbar.vue'
import {
  listPlans, createPlan,
  listSubscriptions, activateSubscription, suspendSubscription, renewSubscription,
  listPartnerLeads, approvePartnerLead,
  listTenants,
} from '../api/superAdmin'

const tabs = ['Parceiros', 'Tenants', 'Planos', 'Assinaturas']
const activeTab = ref('Parceiros')
const error = ref('')

const partnerLeads = ref([])
const tenants = ref([])
const plans = ref([])
const subscriptions = ref([])
const approvalResult = ref(null)

const newPlan = ref({ name: '', price: 0, billing_cycle: 'MONTHLY' })

onMounted(async () => {
  await loadAll()
})

async function loadAll() {
  error.value = ''
  try {
    const [leads, tns, pls, subs] = await Promise.all([
      listPartnerLeads().catch(() => []),
      listTenants().catch(() => []),
      listPlans().catch(() => []),
      listSubscriptions().catch(() => []),
    ])
    partnerLeads.value = leads
    tenants.value = tns
    plans.value = pls
    subscriptions.value = subs
  } catch (e) {
    error.value = 'Erro ao carregar dados'
  }
}

async function handleApprove(leadId) {
  error.value = ''
  try {
    const result = await approvePartnerLead(leadId)
    approvalResult.value = result
    await loadAll()
  } catch (e) {
    error.value = e.response?.data?.detail || 'Erro ao aprovar'
  }
}

async function handleCreatePlan() {
  error.value = ''
  try {
    await createPlan({ ...newPlan.value, description: '' })
    newPlan.value = { name: '', price: 0, billing_cycle: 'MONTHLY' }
    plans.value = await listPlans()
  } catch (e) {
    error.value = e.response?.data?.detail || 'Erro ao criar plano'
  }
}

async function handleActivate(id) {
  try { await activateSubscription(id); subscriptions.value = await listSubscriptions() } catch (e) { error.value = 'Erro ao ativar' }
}
async function handleSuspend(id) {
  try { await suspendSubscription(id); subscriptions.value = await listSubscriptions() } catch (e) { error.value = 'Erro ao suspender' }
}
async function handleRenew(id) {
  try { await renewSubscription(id); subscriptions.value = await listSubscriptions() } catch (e) { error.value = 'Erro ao renovar' }
}

function statusClass(status) {
  const map = {
    ACTIVE: 'text-green-600 font-medium',
    TRIAL: 'text-blue-600 font-medium',
    SUSPENDED: 'text-yellow-600 font-medium',
    CANCELLED: 'text-red-600 font-medium',
    PAST_DUE: 'text-orange-600 font-medium',
  }
  return map[status] || 'text-gray-500'
}
</script>
