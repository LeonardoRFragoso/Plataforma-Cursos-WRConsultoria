<template>
  <div class="space-y-6">
    <AppPageHeader
      eyebrow="Identidade do tenant"
      title="White Label"
      description="Personalize a marca e acompanhe os requisitos reais para publicar o tenant com segurança."
    />

    <AppAlert v-if="error" type="error" closable @close="error=''">{{ error }}</AppAlert>
    <AppAlert v-if="success" type="success" closable @close="success=false">Branding atualizado com sucesso!</AppAlert>

    <section v-if="readiness" class="premium-card p-5 sm:p-6" data-testid="wl-readiness">
      <div class="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p class="premium-kicker">Prontidão para publicação</p>
          <h2 class="mt-1 text-lg font-bold text-slate-900">
            {{ readiness.ready_for_launch ? 'Tenant pronto para lançamento' : 'Configuração ainda incompleta' }}
          </h2>
          <p class="mt-1 text-xs leading-5 text-slate-500">
            O percentual é calculado pelos dados e integrações reais da plataforma; não há marcação manual.
          </p>
        </div>
        <div class="min-w-28 text-right">
          <p class="text-3xl font-black text-slate-900" data-testid="wl-readiness-percent">{{ readiness.percentage }}%</p>
          <p class="text-[10px] font-bold uppercase tracking-wider text-slate-400">{{ readiness.completed }}/{{ readiness.total_required }} requisitos</p>
        </div>
      </div>
      <div class="mt-4 h-2 overflow-hidden rounded-full bg-slate-100">
        <div class="h-full rounded-full transition-all" :style="{ width: `${readiness.percentage}%`, background: 'var(--brand-primary)' }"></div>
      </div>
      <div class="mt-5 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        <article v-for="item in readiness.items" :key="item.key" class="rounded-2xl border p-4" :class="item.ready ? 'border-emerald-200 bg-emerald-50/50' : 'border-amber-200 bg-amber-50/50'" :data-testid="`wl-readiness-${item.key}`">
          <div class="flex items-start gap-3">
            <span class="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl text-sm font-black" :class="item.ready ? 'bg-emerald-100 text-emerald-700' : 'bg-amber-100 text-amber-700'">{{ item.ready ? '✓' : '!' }}</span>
            <div>
              <p class="text-sm font-bold text-slate-800">{{ item.label }}</p>
              <p class="mt-1 text-xs leading-5 text-slate-500">{{ item.detail }}</p>
            </div>
          </div>
        </article>
      </div>
    </section>

    <div class="grid gap-6 xl:grid-cols-[1fr_420px]">
      <form @submit.prevent="handleSave" class="premium-card space-y-6 p-6">
        <div><p class="premium-kicker">Marca</p><h2 class="mt-1 font-bold text-slate-900">Identidade principal</h2></div>
        <div>
          <label class="mb-2 block text-sm font-semibold text-slate-700">Nome da plataforma</label>
          <input v-model="form.name" type="text" class="w-full px-3 py-2" placeholder="Ex: Alfa Academy" data-testid="wl-name-input"/>
          <p class="mt-1.5 text-xs text-slate-400">Exibido no shell, autenticação e metadados.</p>
        </div>
        <div class="grid gap-4 sm:grid-cols-2">
          <div><label class="mb-2 block text-sm font-semibold text-slate-700">URL do logo</label><input v-model="form.logo_url" type="url" class="w-full px-3 py-2" placeholder="https://..." data-testid="wl-logo-input"/><p class="mt-1.5 text-xs text-slate-400">SVG ou PNG transparente.</p></div>
          <div><label class="mb-2 block text-sm font-semibold text-slate-700">Logo branco</label><input v-model="form.logo_white_url" type="url" class="w-full px-3 py-2" placeholder="https://..." data-testid="wl-logo-white-input"/><p class="mt-1.5 text-xs text-slate-400">Para superfícies escuras.</p></div>
        </div>
        <div><label class="mb-2 block text-sm font-semibold text-slate-700">URL do favicon</label><input v-model="form.favicon_url" type="url" class="w-full px-3 py-2" placeholder="https://..." data-testid="wl-favicon-input"/></div>
        <div class="border-t border-slate-100 pt-6"><p class="premium-kicker">Paleta</p><h2 class="mt-1 font-bold text-slate-900">Cores da marca</h2><p class="mt-1 text-xs leading-5 text-slate-400">Botões, navegação ativa, gradientes, progresso, avatares e estados de foco serão derivados dessas cores.</p></div>
        <div class="grid gap-4 sm:grid-cols-3">
          <div v-for="color in colorFields" :key="color.key">
            <label class="mb-2 block text-xs font-bold text-slate-600">{{ color.label }}</label>
            <div class="flex items-center gap-2 rounded-xl border border-slate-200 bg-white p-2">
              <input v-model="form[color.key]" type="color" class="h-9 w-10 cursor-pointer rounded-lg border-0 p-0" :data-testid="color.testid"/>
              <input v-model="form[color.key]" type="text" class="min-w-0 flex-1 border-0 px-1 text-xs font-mono shadow-none focus:ring-0" :placeholder="color.placeholder"/>
            </div>
          </div>
        </div>
        <div class="flex justify-end border-t border-slate-100 pt-5">
          <button type="submit" :disabled="saving" class="rounded-xl px-5 py-2.5 text-sm font-bold text-white shadow-md disabled:opacity-50" :style="{background:'var(--brand-primary)'}" data-testid="wl-save-btn">{{ saving?'Salvando...':'Salvar branding' }}</button>
        </div>
      </form>

      <aside class="xl:sticky xl:top-28 xl:h-fit">
        <div class="overflow-hidden rounded-[22px] border border-slate-200 bg-white shadow-xl">
          <div class="p-5 text-white" :style="previewGradient">
            <div class="flex items-center gap-3"><div class="flex h-11 w-11 items-center justify-center rounded-xl bg-white/10 p-1"><img v-if="form.logo_white_url||form.logo_url" :src="form.logo_white_url||form.logo_url" alt="Preview do logo" class="max-h-8 max-w-9 object-contain"/><span v-else class="text-sm font-black">{{ previewInitials }}</span></div><div><p class="text-sm font-bold">{{ form.name||'Sua plataforma' }}</p><p class="text-[10px] uppercase tracking-[.15em] text-white/50">Learning platform</p></div></div>
            <div class="mt-8 rounded-2xl bg-white/10 p-4 backdrop-blur"><p class="text-[10px] font-bold uppercase tracking-wider text-white/55">Preview</p><p class="mt-1 text-lg font-bold">Experiência premium, identidade própria.</p></div>
          </div>
          <div class="p-5">
            <div class="grid grid-cols-3 gap-2"><div v-for="color in colorFields" :key="color.key" class="rounded-xl border border-slate-100 p-2"><div class="h-8 rounded-lg" :style="{background:form[color.key]||color.placeholder}"></div><p class="mt-2 text-[9px] font-bold uppercase tracking-wide text-slate-400">{{ color.short }}</p></div></div>
            <button type="button" class="mt-5 w-full rounded-xl px-4 py-2.5 text-sm font-bold text-white" :style="{background:form.primary_color||'#1B7A3A'}">Botão principal</button>
            <div class="mt-3 h-2 overflow-hidden rounded-full bg-slate-100"><div class="h-full w-2/3 rounded-full" :style="{background:form.primary_color||'#1B7A3A'}"></div></div>
            <p class="mt-3 text-xs leading-5 text-slate-400">A mesma linguagem visual é aplicada às áreas de aluno, admin, empresa e autenticação.</p>
          </div>
        </div>
      </aside>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import AppPageHeader from '../components/AppPageHeader.vue'
import AppAlert from '../components/AppAlert.vue'
import { useTenantStore } from '../stores/tenant'
import { fetchTenantReadiness, updateTenantBranding } from '../api/tenant'
import { TENANT_SLUG } from '../utils/tenantSlug'

const tenantStore = useTenantStore()
const saving = ref(false)
const success = ref(false)
const error = ref('')
const readiness = ref(null)
const form = ref({ name:'', logo_url:'', logo_white_url:'', favicon_url:'', primary_color:'', secondary_color:'', accent_color:'' })
const colorFields = [
  { key:'primary_color', label:'Primária', short:'Principal', testid:'wl-primary-color', placeholder:'#1B7A3A' },
  { key:'secondary_color', label:'Secundária', short:'Base', testid:'wl-secondary-color', placeholder:'#17324D' },
  { key:'accent_color', label:'Destaque', short:'Acento', testid:'wl-accent-color', placeholder:'#F59E0B' },
]
const previewInitials = computed(() => (form.value.name || 'PL').split(/\s+/).slice(0,2).map(p => p[0]).join('').toUpperCase())
const previewGradient = computed(() => ({ background:`linear-gradient(145deg,${form.value.secondary_color||'#17324D'},${form.value.primary_color||'#1B7A3A'})` }))

async function refreshReadiness() {
  try { readiness.value = await fetchTenantReadiness() } catch (err) { error.value = err.response?.data?.detail || 'Erro ao calcular prontidão do tenant.' }
}

onMounted(async () => {
  form.value = { name:tenantStore.name||'', logo_url:tenantStore.logo_url||'', logo_white_url:tenantStore.logo_white_url||'', favicon_url:tenantStore.favicon_url||'', primary_color:tenantStore.primary_color||'', secondary_color:tenantStore.secondary_color||'', accent_color:tenantStore.accent_color||'' }
  await refreshReadiness()
})

async function handleSave() {
  saving.value = true
  success.value = false
  error.value = ''
  if (form.value.name && form.value.name.trim().length > 100) {
    error.value = 'O nome da plataforma deve ter no máximo 100 caracteres.'
    saving.value = false
    return
  }
  try {
    const payload = {}
    for (const [key, val] of Object.entries(form.value)) if (val && val.trim()) payload[key] = val.trim()
    await updateTenantBranding(payload)
    await tenantStore.refreshBranding(TENANT_SLUG)
    await refreshReadiness()
    success.value = true
  } catch (err) {
    error.value = err.response?.data?.detail || 'Erro ao salvar branding'
  } finally {
    saving.value = false
  }
}
</script>
