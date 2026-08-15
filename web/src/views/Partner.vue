<template>
  <div class="min-h-screen bg-gradient-to-br from-slate-900 to-slate-800 p-6">
    <div class="max-w-xl mx-auto bg-white rounded-2xl shadow-xl p-8 mt-10">
      <h1 class="text-2xl font-bold text-gray-800 mb-2">Seja um parceiro</h1>
      <p class="text-gray-600 mb-6">
        Preencha seus dados e entraremos em contato para ativar sua plataforma
        white label.
      </p>

      <form class="space-y-4" @submit.prevent="handleSubmit">
        <div>
          <label class="block text-sm font-medium text-gray-700">Empresa</label>
          <input
            v-model="form.company_name"
            type="text"
            required
            class="w-full p-3 border rounded-lg focus:outline-none focus:ring-2 focus:ring-primary"
          />
        </div>
        <div>
          <label class="block text-sm font-medium text-gray-700">CNPJ</label>
          <input
            v-model="form.cnpj"
            type="text"
            class="w-full p-3 border rounded-lg focus:outline-none focus:ring-2 focus:ring-primary"
          />
        </div>
        <div>
          <label class="block text-sm font-medium text-gray-700">Nome do contato</label>
          <input
            v-model="form.contact_name"
            type="text"
            required
            class="w-full p-3 border rounded-lg focus:outline-none focus:ring-2 focus:ring-primary"
          />
        </div>
        <div>
          <label class="block text-sm font-medium text-gray-700">E-mail</label>
          <input
            v-model="form.contact_email"
            type="email"
            required
            class="w-full p-3 border rounded-lg focus:outline-none focus:ring-2 focus:ring-primary"
          />
        </div>
        <div>
          <label class="block text-sm font-medium text-gray-700">Telefone</label>
          <input
            v-model="form.contact_phone"
            type="text"
            class="w-full p-3 border rounded-lg focus:outline-none focus:ring-2 focus:ring-primary"
          />
        </div>
        <div>
          <label class="block text-sm font-medium text-gray-700">Mensagem</label>
          <textarea
            v-model="form.message"
            rows="3"
            class="w-full p-3 border rounded-lg focus:outline-none focus:ring-2 focus:ring-primary"
          />
        </div>

        <button
          type="submit"
          class="w-full py-3 bg-primary text-white font-semibold rounded-lg hover:opacity-90 transition"
        >
          Enviar proposta
        </button>
      </form>

      <p v-if="message" class="mt-4 text-center text-sm" :class="success ? 'text-green-600' : 'text-red-600'">
        {{ message }}
      </p>
    </div>
  </div>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { submitPartnerLead } from '../api/partner'

const form = reactive({
  company_name: '',
  cnpj: '',
  contact_name: '',
  contact_email: '',
  contact_phone: '',
  message: '',
})

const message = ref('')
const success = ref(false)

async function handleSubmit() {
  try {
    await submitPartnerLead(form)
    success.value = true
    message.value = 'Proposta enviada com sucesso! Entraremos em contato em breve.'
    Object.keys(form).forEach((k) => (form[k] = ''))
  } catch (error) {
    success.value = false
    message.value = 'Erro ao enviar proposta. Tente novamente.'
  }
}
</script>
