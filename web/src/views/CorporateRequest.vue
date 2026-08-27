<template>
  <main class="brand-gradient relative min-h-screen overflow-hidden px-4 py-8 sm:py-12">
    <div class="absolute -right-24 -top-24 h-96 w-96 rounded-full bg-white/[.08]"></div>
    <div class="absolute -bottom-32 -left-20 h-96 w-96 rounded-full bg-black/10"></div>
    <div class="relative mx-auto grid max-w-5xl gap-6 lg:grid-cols-[.8fr_1.2fr]">
      <aside class="flex flex-col justify-between rounded-[24px] border border-white/10 bg-white/[.08] p-6 text-white backdrop-blur sm:p-8">
        <div>
          <router-link to="/" class="text-xs font-bold text-white/65 hover:text-white">← Voltar</router-link>
          <p class="mt-8 text-xs font-bold uppercase tracking-[.2em] text-white/45">Treinamento corporativo</p>
          <h1 class="mt-3 text-3xl font-bold leading-tight tracking-tight">Treinamentos para empresas</h1>
          <p class="mt-4 text-sm leading-7 text-white/65">Informe sua necessidade. A operação corporativa permite estruturar turmas, vagas, colaboradores e acompanhamento de certificações.</p>
        </div>
        <div class="mt-8 space-y-3">
          <div v-for="item in highlights" :key="item.title" class="flex gap-3 rounded-2xl border border-white/10 bg-white/[.06] p-4">
            <span class="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-white/10"><NavIcon :name="item.icon" /></span>
            <div><p class="text-sm font-bold">{{ item.title }}</p><p class="mt-1 text-xs leading-5 text-white/50">{{ item.text }}</p></div>
          </div>
        </div>
      </aside>
      <section class="premium-card p-6 sm:p-8 lg:p-10">
        <div v-if="sent" class="flex min-h-[520px] items-center justify-center text-center">
          <div>
            <div class="mx-auto flex h-16 w-16 items-center justify-center rounded-2xl bg-emerald-50 text-emerald-600"><NavIcon name="shield" /></div>
            <h2 class="mt-5 text-2xl font-bold text-slate-900">Solicitação registrada</h2>
            <p class="mx-auto mt-2 max-w-md text-sm leading-6 text-slate-500">Nossa equipe poderá entrar em contato pelos dados informados para estruturar a proposta de treinamento.</p>
            <router-link to="/" class="mt-6 inline-block text-sm font-bold text-[var(--brand-primary)]">Voltar para o início →</router-link>
          </div>
        </div>
        <form v-else class="grid grid-cols-1 gap-4 md:grid-cols-2" @submit.prevent="submit">
          <div class="md:col-span-2 mb-2"><p class="premium-kicker">Diagnóstico inicial</p><h2 class="mt-2 text-2xl font-bold tracking-tight text-slate-900">Conte sua necessidade</h2><p class="mt-2 text-sm leading-6 text-slate-500">Essas informações ajudam a dimensionar a turma e o atendimento corporativo.</p></div>
          <label class="md:col-span-2"><span class="mb-2 block text-sm font-semibold text-slate-700">Empresa *</span><input v-model.trim="form.company_name" required minlength="2" class="w-full" /></label>
          <label><span class="mb-2 block text-sm font-semibold text-slate-700">CNPJ</span><input v-model.trim="form.cnpj" inputmode="numeric" placeholder="00.000.000/0000-00" class="w-full" /></label>
          <label><span class="mb-2 block text-sm font-semibold text-slate-700">Quantidade de colaboradores</span><input v-model.number="form.employee_count" type="number" min="1" class="w-full" /></label>
          <label><span class="mb-2 block text-sm font-semibold text-slate-700">Responsável *</span><input v-model.trim="form.contact_name" required minlength="2" class="w-full" /></label>
          <label><span class="mb-2 block text-sm font-semibold text-slate-700">E-mail *</span><input v-model.trim="form.contact_email" required type="email" class="w-full" /></label>
          <label><span class="mb-2 block text-sm font-semibold text-slate-700">Telefone</span><input v-model.trim="form.contact_phone" class="w-full" /></label>
          <label><span class="mb-2 block text-sm font-semibold text-slate-700">Treinamento de interesse</span><input v-model.trim="form.course_interest" class="w-full" /></label>
          <label class="md:col-span-2"><span class="mb-2 block text-sm font-semibold text-slate-700">Detalhes</span><textarea v-model.trim="form.message" rows="5" class="w-full"></textarea></label>
          <div v-if="error" class="md:col-span-2 rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-700">{{ error }}</div>
          <div class="md:col-span-2 pt-2"><button :disabled="loading" class="w-full rounded-xl px-5 py-3 text-sm font-bold text-white shadow-md disabled:opacity-60" :style="{ background: 'var(--brand-primary)' }">{{ loading ? 'Enviando…' : 'Enviar solicitação' }}</button></div>
        </form>
      </section>
    </div>
  </main>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { createCorporateRequest } from '../api/corporate'
import NavIcon from '../components/NavIcon.vue'
import { apiDetailMessage, isValidCnpj, normalizeCnpj } from '../utils/brazilianDocuments'

const highlights = [
  { icon: 'users', title: 'Gestão de colaboradores', text: 'Convites, vínculo, offboarding e acompanhamento por funcionário.' },
  { icon: 'calendar', title: 'Vagas e turmas', text: 'Capacidade contratada e matrícula corporativa em lote.' },
  { icon: 'shield', title: 'Certificação', text: 'Histórico confiável de certificados e vencimentos.' },
]
const form = reactive({ company_name: '', cnpj: '', contact_name: '', contact_email: '', contact_phone: '', course_interest: '', employee_count: null, message: '' })
const loading = ref(false)
const error = ref('')
const sent = ref(false)

async function submit() {
  error.value = ''
  if (form.cnpj && !isValidCnpj(form.cnpj)) {
    error.value = 'CNPJ inválido. Confira os 14 dígitos e tente novamente.'
    return
  }

  loading.value = true
  try {
    await createCorporateRequest({
      ...form,
      employee_count: form.employee_count || null,
      cnpj: form.cnpj ? normalizeCnpj(form.cnpj) : null,
    })
    sent.value = true
  } catch (err) {
    error.value = apiDetailMessage(err, 'Não foi possível registrar a solicitação.')
  } finally {
    loading.value = false
  }
}
</script>
