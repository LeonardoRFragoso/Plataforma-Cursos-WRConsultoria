<template>
  <div>
    <div class="max-w-3xl mx-auto">
      <AppPageHeader title="Configurações Financeiras" description="Gerencie a integração com o gateway de pagamento." />

      <AppAlert v-if="error" type="error" closable @close="error = ''">{{ error }}</AppAlert>
      <AppAlert v-if="success" type="success" closable @close="success = ''">{{ success }}</AppAlert>

      <!-- Status Card -->
      <div class="mt-6 bg-white p-6 rounded-lg shadow-md border border-gray-200">
        <h3 class="text-lg font-semibold text-gray-900 mb-4">Status da Integração</h3>

        <div v-if="loading" class="text-gray-500">Carregando...</div>
        <div v-else class="space-y-3">
          <div class="flex items-center justify-between">
            <span class="text-sm text-gray-600">Gateway ativo</span>
            <span class="text-sm font-medium" :class="status.active_provider === 'ASAAS' ? 'text-green-600' : 'text-gray-500'">
              {{ status.active_provider === 'ASAAS' ? 'Asaas' : 'Mercado Pago' }}
            </span>
          </div>
          <div class="flex items-center justify-between">
            <span class="text-sm text-gray-600">Asaas configurado</span>
            <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium"
              :class="status.configured ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-600'">
              {{ status.configured ? 'Sim' : 'Não' }}
            </span>
          </div>
          <div class="flex items-center justify-between">
            <span class="text-sm text-gray-600">Webhook configurado</span>
            <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium"
              :class="status.webhook_configured ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-600'">
              {{ status.webhook_configured ? 'Sim' : 'Não' }}
            </span>
          </div>
        </div>

        <div class="mt-4 flex gap-3">
          <button
            v-if="!status.configured"
            @click="showConnectForm = true"
            class="px-4 py-2 bg-primary-600 text-white rounded-md text-sm font-medium hover:bg-primary-700"
            data-testid="btn-connect-asaas"
          >
            Conectar Asaas
          </button>
          <button
            v-if="status.configured"
            @click="handleValidate"
            :disabled="validating"
            class="px-4 py-2 bg-blue-600 text-white rounded-md text-sm font-medium hover:bg-blue-700 disabled:opacity-50"
            data-testid="btn-validate-asaas"
          >
            {{ validating ? 'Validando...' : 'Validar conexão' }}
          </button>
          <button
            v-if="status.configured"
            @click="showConnectForm = true"
            class="px-4 py-2 bg-yellow-600 text-white rounded-md text-sm font-medium hover:bg-yellow-700"
            data-testid="btn-replace-key"
          >
            Substituir chave
          </button>
          <button
            v-if="status.configured"
            @click="handleDisconnect"
            :disabled="disconnecting"
            class="px-4 py-2 bg-red-600 text-white rounded-md text-sm font-medium hover:bg-red-700 disabled:opacity-50"
            data-testid="btn-disconnect-asaas"
          >
            {{ disconnecting ? 'Desconectando...' : 'Desconectar' }}
          </button>
        </div>
      </div>

      <!-- Connect Form -->
      <div v-if="showConnectForm" class="mt-6 bg-white p-6 rounded-lg shadow-md border border-gray-200">
        <h3 class="text-lg font-semibold text-gray-900 mb-4">
          {{ status.configured ? 'Substituir Chave Asaas' : 'Conectar Asaas' }}
        </h3>
        <p class="text-sm text-gray-600 mb-4">
         Informe a chave de API de produção da sua conta Asaas. A chave é armazenada de forma criptografada e nunca pode ser visualizada após salva.
        </p>
        <form @submit.prevent="handleConnect" class="space-y-4">
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">Chave de API</label>
            <input
              v-model="apiKey"
              type="password"
              class="w-full rounded-md border-gray-300 border px-3 py-2 focus:ring-primary-500 focus:border-primary-500"
              placeholder="Cole aqui a chave de API do Asaas"
              data-testid="asaas-api-key-input"
              autocomplete="off"
            />
            <p class="text-xs text-gray-500 mt-1">A chave não é exibida após salvar e não é armazenada no navegador.</p>
          </div>
          <div class="flex gap-3">
            <button
              type="submit"
              :disabled="connecting || !apiKey"
              class="px-4 py-2 bg-primary-600 text-white rounded-md text-sm font-medium hover:bg-primary-700 disabled:opacity-50"
              data-testid="btn-submit-connect"
            >
              {{ connecting ? 'Conectando...' : 'Conectar' }}
            </button>
            <button
              type="button"
              @click="showConnectForm = false; apiKey = ''"
              class="px-4 py-2 bg-gray-200 text-gray-700 rounded-md text-sm font-medium hover:bg-gray-300"
            >
              Cancelar
            </button>
          </div>
        </form>
      </div>

      <!-- Info Card -->
      <div class="mt-6 bg-blue-50 p-4 rounded-lg border border-blue-200">
        <h4 class="text-sm font-semibold text-blue-900 mb-2">Como funciona</h4>
        <ul class="text-sm text-blue-800 space-y-1 list-disc list-inside">
          <li>A integração usa o Asaas como gateway de pagamento hospedado.</li>
          <li>Os alunos pagam via Pix, boleto ou cartão na página do Asaas.</li>
          <li>Webhooks confirmam pagamentos automaticamente.</li>
          <li>A chave de API é criptografada e write-only (não pode ser visualizada).</li>
          <li>O webhook é autenticado com um token separado, gerado automaticamente.</li>
        </ul>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { asaasApi } from '../api/asaas'

const loading = ref(true)
const status = ref({})
const showConnectForm = ref(false)
const apiKey = ref('')
const connecting = ref(false)
const validating = ref(false)
const disconnecting = ref(false)
const error = ref('')
const success = ref('')

async function fetchStatus() {
  loading.value = true
  try {
    const resp = await asaasApi.getStatus()
    status.value = resp.data
  } catch (e) {
    error.value = 'Erro ao carregar status da integração.'
  } finally {
    loading.value = false
  }
}

async function handleConnect() {
  connecting.value = true
  error.value = ''
  success.value = ''
  try {
    const resp = await asaasApi.connect(apiKey.value)
    success.value = resp.data.message || 'Asaas conectado com sucesso.'
    apiKey.value = ''
    showConnectForm.value = false
    await fetchStatus()
  } catch (e) {
    error.value = e.response?.data?.detail || 'Erro ao conectar Asaas.'
  } finally {
    connecting.value = false
  }
}

async function handleValidate() {
  validating.value = true
  error.value = ''
  success.value = ''
  try {
    const resp = await asaasApi.validate()
    if (resp.data.valid) {
      success.value = 'Conexão válida!'
    } else {
      error.value = resp.data.message || 'Validação falhou.'
    }
  } catch (e) {
    error.value = e.response?.data?.detail || 'Erro ao validar conexão.'
  } finally {
    validating.value = false
  }
}

async function handleDisconnect() {
  if (!confirm('Tem certeza? Isso desconectará o Asaas e reverterá para Mercado Pago.')) return
  disconnecting.value = true
  error.value = ''
  success.value = ''
  try {
    await asaasApi.disconnect()
    success.value = 'Asaas desconectado.'
    await fetchStatus()
  } catch (e) {
    error.value = e.response?.data?.detail || 'Erro ao desconectar.'
  } finally {
    disconnecting.value = false
  }
}

onMounted(fetchStatus)
</script>
