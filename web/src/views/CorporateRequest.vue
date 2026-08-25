<template>
  <main class="min-h-screen bg-gray-50 py-12 px-4">
    <div class="mx-auto max-w-3xl rounded-2xl bg-white border border-gray-200 shadow-sm p-6 sm:p-10">
      <router-link to="/" class="text-sm text-primary-600 hover:underline">← Voltar</router-link>
      <h1 class="mt-6 text-3xl font-bold text-gray-900">Treinamentos para empresas</h1>
      <p class="mt-2 text-gray-600">Informe sua necessidade. A equipe responsável poderá estruturar turmas, vagas e acompanhamento corporativo.</p>

      <div v-if="sent" class="mt-8 rounded-xl border border-green-200 bg-green-50 p-5 text-green-800">
        Solicitação registrada. Nossa equipe poderá entrar em contato pelos dados informados.
      </div>

      <form v-else class="mt-8 grid grid-cols-1 md:grid-cols-2 gap-5" @submit.prevent="submit">
        <label class="block md:col-span-2"><span class="text-sm font-medium">Empresa *</span><input v-model.trim="form.company_name" required minlength="2" class="mt-1 w-full rounded-lg border-gray-300" /></label>
        <label class="block"><span class="text-sm font-medium">CNPJ</span><input v-model.trim="form.cnpj" class="mt-1 w-full rounded-lg border-gray-300" /></label>
        <label class="block"><span class="text-sm font-medium">Quantidade de colaboradores</span><input v-model.number="form.employee_count" type="number" min="1" class="mt-1 w-full rounded-lg border-gray-300" /></label>
        <label class="block"><span class="text-sm font-medium">Responsável *</span><input v-model.trim="form.contact_name" required minlength="2" class="mt-1 w-full rounded-lg border-gray-300" /></label>
        <label class="block"><span class="text-sm font-medium">E-mail *</span><input v-model.trim="form.contact_email" required type="email" class="mt-1 w-full rounded-lg border-gray-300" /></label>
        <label class="block"><span class="text-sm font-medium">Telefone</span><input v-model.trim="form.contact_phone" class="mt-1 w-full rounded-lg border-gray-300" /></label>
        <label class="block"><span class="text-sm font-medium">Treinamento de interesse</span><input v-model.trim="form.course_interest" class="mt-1 w-full rounded-lg border-gray-300" /></label>
        <label class="block md:col-span-2"><span class="text-sm font-medium">Detalhes</span><textarea v-model.trim="form.message" rows="5" class="mt-1 w-full rounded-lg border-gray-300"></textarea></label>
        <div v-if="error" class="md:col-span-2 rounded-lg bg-red-50 text-red-700 p-3 text-sm">{{ error }}</div>
        <div class="md:col-span-2"><button :disabled="loading" class="rounded-lg bg-primary-600 text-white px-5 py-3 font-medium disabled:opacity-60">{{ loading ? 'Enviando…' : 'Enviar solicitação' }}</button></div>
      </form>
    </div>
  </main>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { createCorporateRequest } from '../api/corporate'

const form = reactive({ company_name: '', cnpj: '', contact_name: '', contact_email: '', contact_phone: '', course_interest: '', employee_count: null, message: '' })
const loading = ref(false)
const error = ref('')
const sent = ref(false)

async function submit() {
  loading.value = true
  error.value = ''
  try {
    await createCorporateRequest({ ...form, employee_count: form.employee_count || null, cnpj: form.cnpj || null })
    sent.value = true
  } catch (err) {
    error.value = err.response?.data?.detail || 'Não foi possível registrar a solicitação.'
  } finally {
    loading.value = false
  }
}
</script>
