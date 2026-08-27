<template>
  <div class="space-y-7">
    <AppPageHeader
      eyebrow="Certificação"
      title="Certificate Studio"
      description="Crie e publique versões visuais de certificados sem alterar dados acadêmicos ou regulatórios. Cada emissão congela a versão publicada usada no PDF."
    />

    <div v-if="error" class="rounded-2xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">{{ error }}</div>
    <div v-if="notice" class="rounded-2xl border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-800">{{ notice }}</div>

    <section class="grid gap-5 xl:grid-cols-[340px_minmax(0,1fr)]">
      <div class="premium-card p-5 sm:p-6">
        <div class="flex items-center justify-between gap-3">
          <div>
            <p class="premium-kicker">Biblioteca visual</p>
            <h2 class="mt-1 font-bold text-slate-900">Templates</h2>
          </div>
          <button class="rounded-xl px-3 py-2 text-xs font-bold text-white" :style="{ background: 'var(--brand-primary)' }" @click="showCreate = !showCreate">Novo</button>
        </div>

        <form v-if="showCreate" class="mt-4 space-y-3 rounded-2xl border border-slate-200 bg-slate-50 p-4" @submit.prevent="createTemplate">
          <label class="block text-xs font-bold text-slate-600">Nome<input v-model.trim="newTemplate.name" required minlength="2" class="mt-1 w-full text-sm" /></label>
          <label class="block text-xs font-bold text-slate-600">Slug<input v-model.trim="newTemplate.slug" required pattern="[a-z0-9]+(?:-[a-z0-9]+)*" class="mt-1 w-full text-sm" placeholder="certificado-nr" /></label>
          <button :disabled="busy" class="w-full rounded-xl px-3 py-2 text-xs font-bold text-white disabled:opacity-50" :style="{ background: 'var(--brand-primary)' }">Criar template</button>
        </form>

        <div v-if="loading" class="py-8 text-sm text-slate-400">Carregando…</div>
        <div v-else class="mt-4 space-y-2">
          <button
            v-for="item in templates"
            :key="item.id"
            class="w-full rounded-2xl border p-4 text-left transition"
            :class="selectedTemplate?.id === item.id ? 'border-emerald-300 bg-emerald-50' : 'border-slate-200 bg-white hover:border-slate-300'"
            @click="selectTemplate(item)"
          >
            <div class="flex items-center justify-between gap-2">
              <span class="font-bold text-slate-900">{{ item.name }}</span>
              <span class="rounded-full px-2 py-1 text-[10px] font-bold" :class="item.is_active ? 'bg-emerald-100 text-emerald-700' : 'bg-slate-100 text-slate-500'">{{ item.is_active ? 'ATIVO' : 'ARQUIVADO' }}</span>
            </div>
            <p class="mt-1 font-mono text-[11px] text-slate-400">{{ item.slug }}</p>
          </button>
          <p v-if="!templates.length" class="rounded-2xl border border-dashed border-slate-200 p-6 text-center text-sm text-slate-400">Nenhum template criado.</p>
        </div>
      </div>

      <div class="space-y-5">
        <section class="premium-card p-5 sm:p-6">
          <div class="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <p class="premium-kicker">Versão visual</p>
              <h2 class="mt-1 font-bold text-slate-900">{{ selectedTemplate ? selectedTemplate.name : 'Selecione um template' }}</h2>
              <p class="mt-1 text-xs text-slate-400">Somente versões DRAFT podem ser editadas. Uma versão PUBLISHED é imutável.</p>
            </div>
            <div v-if="selectedTemplate" class="flex flex-wrap gap-2">
              <button :disabled="busy || !selectedTemplate.is_active" class="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs font-bold text-slate-700 disabled:opacity-40" @click="createDraft">Nova versão</button>
              <button class="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs font-bold text-slate-600" @click="toggleArchive">{{ selectedTemplate.is_active ? 'Arquivar' : 'Reativar' }}</button>
            </div>
          </div>

          <div v-if="selectedTemplate" class="mt-5 grid gap-5 lg:grid-cols-[220px_minmax(0,1fr)]">
            <div class="space-y-2">
              <button
                v-for="version in versions"
                :key="version.id"
                class="w-full rounded-xl border px-3 py-3 text-left"
                :class="selectedVersion?.id === version.id ? 'border-emerald-300 bg-emerald-50' : 'border-slate-200 bg-white'"
                @click="selectVersion(version)"
              >
                <div class="flex items-center justify-between">
                  <b class="text-sm text-slate-800">Versão {{ version.version }}</b>
                  <span class="rounded-full px-2 py-1 text-[10px] font-bold" :class="version.status === 'PUBLISHED' ? 'bg-emerald-100 text-emerald-700' : 'bg-amber-100 text-amber-700'">{{ version.status }}</span>
                </div>
                <p class="mt-1 text-[11px] text-slate-400">{{ version.visual_config?.preset || 'CLASSIC' }}</p>
              </button>
              <p v-if="!versions.length" class="text-xs text-slate-400">Crie a primeira versão para começar.</p>
            </div>

            <form v-if="selectedVersion" class="space-y-5" @submit.prevent="saveDraft">
              <div class="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                <label class="text-xs font-bold text-slate-600">Preset<select v-model="form.preset" :disabled="published" class="mt-1 w-full text-sm"><option>CLASSIC</option><option>MODERN</option><option>MINIMAL</option></select></label>
                <label class="text-xs font-bold text-slate-600">Fonte<select v-model="form.font_family" :disabled="published" class="mt-1 w-full text-sm"><option>HELVETICA</option><option>TIMES</option><option>COURIER</option></select></label>
                <label class="text-xs font-bold text-slate-600">Borda<select v-model="form.border_style" :disabled="published" class="mt-1 w-full text-sm"><option>NONE</option><option>SIMPLE</option><option>DOUBLE</option></select></label>
                <label class="text-xs font-bold text-slate-600">Cor principal<input v-model="form.primary_color" :disabled="published" type="color" class="mt-1 h-10 w-full" /></label>
                <label class="text-xs font-bold text-slate-600">Cor secundária<input v-model="form.secondary_color" :disabled="published" type="color" class="mt-1 h-10 w-full" /></label>
                <label class="text-xs font-bold text-slate-600">Cor de destaque<input v-model="form.accent_color" :disabled="published" type="color" class="mt-1 h-10 w-full" /></label>
                <label class="text-xs font-bold text-slate-600">Fundo<input v-model="form.background_color" :disabled="published" type="color" class="mt-1 h-10 w-full" /></label>
                <label class="text-xs font-bold text-slate-600">Estilo do fundo<select v-model="form.background_style" :disabled="published" class="mt-1 w-full text-sm"><option>WHITE</option><option>LIGHT_TINT</option></select></label>
                <label class="text-xs font-bold text-slate-600">QR Code<select v-model="form.qr_position" :disabled="published" class="mt-1 w-full text-sm"><option>LEFT</option><option>RIGHT</option></select></label>
                <label class="text-xs font-bold text-slate-600">Posição da logo<select v-model="form.logo_position" :disabled="published" class="mt-1 w-full text-sm"><option>LEFT</option><option>CENTER</option><option>RIGHT</option></select></label>
              </div>

              <div class="grid gap-4 sm:grid-cols-2">
                <label class="rounded-2xl border border-dashed border-slate-200 p-4 text-xs font-bold text-slate-600">Logo principal <span class="font-normal text-slate-400">PNG/JPEG até 250 KiB</span><input :disabled="published" type="file" accept="image/png,image/jpeg" class="mt-2 block w-full text-xs" @change="loadLogo($event, 'logo_data_uri')" /></label>
                <label class="rounded-2xl border border-dashed border-slate-200 p-4 text-xs font-bold text-slate-600">Logo secundária <span class="font-normal text-slate-400">co-branding autorizado</span><input :disabled="published" type="file" accept="image/png,image/jpeg" class="mt-2 block w-full text-xs" @change="loadLogo($event, 'secondary_logo_data_uri')" /></label>
              </div>

              <div class="flex flex-wrap gap-4 text-xs font-semibold text-slate-600">
                <label><input v-model="form.show_issuer_logo" :disabled="published" type="checkbox" class="mr-2" />Exibir logo principal</label>
                <label><input v-model="form.show_secondary_logo" :disabled="published" type="checkbox" class="mr-2" />Exibir co-branding</label>
                <label><input v-model="form.show_verification_seal" :disabled="published" type="checkbox" class="mr-2" />Selo de verificação</label>
              </div>

              <div class="flex flex-wrap justify-end gap-2 border-t border-slate-100 pt-4">
                <button type="button" :disabled="busy" class="rounded-xl border border-slate-200 bg-white px-4 py-2 text-xs font-bold text-slate-700" @click="preview">Abrir prévia PDF</button>
                <button v-if="!published" :disabled="busy" class="rounded-xl border border-slate-200 bg-white px-4 py-2 text-xs font-bold text-slate-700">Salvar rascunho</button>
                <button v-if="!published" type="button" :disabled="busy" class="rounded-xl px-4 py-2 text-xs font-bold text-white disabled:opacity-40" :style="{ background: 'var(--brand-primary)' }" @click="publish">Publicar versão</button>
              </div>
            </form>
          </div>
        </section>

        <section class="premium-card p-5 sm:p-6">
          <p class="premium-kicker">Aplicação por curso</p>
          <h2 class="mt-1 font-bold text-slate-900">Template do certificado</h2>
          <p class="mt-1 text-xs text-slate-400">A emissão usa a versão publicada mais recente do template atribuído e congela essa versão no snapshot.</p>
          <div class="mt-5 grid gap-3 md:grid-cols-[1fr_1fr_auto_auto] md:items-end">
            <label class="text-xs font-bold text-slate-600">Curso<select v-model="selectedCourseId" class="mt-1 w-full text-sm" @change="loadResolution"><option value="">Selecione</option><option v-for="course in courses" :key="course.id" :value="course.id">{{ course.code }} — {{ course.name }}</option></select></label>
            <label class="text-xs font-bold text-slate-600">Template<select v-model="assignmentTemplateId" class="mt-1 w-full text-sm"><option value="">Padrão do sistema</option><option v-for="item in templates.filter(t => t.is_active)" :key="item.id" :value="item.id">{{ item.name }}</option></select></label>
            <button :disabled="busy || !selectedCourseId" class="rounded-xl px-4 py-2.5 text-xs font-bold text-white disabled:opacity-40" :style="{ background: 'var(--brand-primary)' }" @click="saveAssignment">Aplicar</button>
            <button :disabled="busy || !selectedCourseId" class="rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-xs font-bold text-slate-600 disabled:opacity-40" @click="resetAssignment">Padrão</button>
          </div>
          <div v-if="resolution" class="mt-4 rounded-2xl bg-slate-50 p-4 text-xs leading-5 text-slate-600">
            Em uso: <b>{{ resolution.template_name }}</b>, versão <b>{{ resolution.version }}</b> · origem {{ resolution.source }} · preset {{ resolution.visual_config?.preset }}.
          </div>
        </section>
      </div>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import api from '../api/client'
import {
  assignCertificateTemplate,
  createCertificateTemplate,
  createCertificateTemplateVersion,
  getCertificateTemplateResolution,
  listCertificateTemplates,
  listCertificateTemplateVersions,
  previewCertificateTemplate,
  publishCertificateTemplateVersion,
  resetCertificateTemplate,
  updateCertificateTemplate,
  updateCertificateTemplateVersion,
} from '../api/certificateStudio'
import AppPageHeader from '../components/AppPageHeader.vue'

const defaults = () => ({
  preset: 'CLASSIC', primary_color: '#047F37', secondary_color: '#036B2E', accent_color: '#D1E7DA', background_color: '#FFFFFF',
  font_family: 'HELVETICA', border_style: 'SIMPLE', background_style: 'WHITE', logo_position: 'CENTER', qr_position: 'RIGHT',
  show_issuer_logo: true, show_secondary_logo: false, show_verification_seal: true, logo_data_uri: null, secondary_logo_data_uri: null,
})
const templates = ref([]), versions = ref([]), courses = ref([])
const selectedTemplate = ref(null), selectedVersion = ref(null), selectedCourseId = ref(''), assignmentTemplateId = ref(''), resolution = ref(null)
const loading = ref(true), busy = ref(false), showCreate = ref(false), error = ref(''), notice = ref('')
const newTemplate = reactive({ name: '', slug: '' })
const form = reactive(defaults())
const published = computed(() => selectedVersion.value?.status === 'PUBLISHED')

function messageFrom(errorValue, fallback) {
  const detail = errorValue?.response?.data?.detail
  return typeof detail === 'string' ? detail : fallback
}
function clearMessages() { error.value = ''; notice.value = '' }
function fillForm(config) { Object.assign(form, defaults(), config || {}) }
async function load() {
  loading.value = true
  try {
    const [templateResponse, courseResponse] = await Promise.all([listCertificateTemplates(true), api.get('/api/v1/courses/')])
    templates.value = templateResponse.data
    courses.value = Array.isArray(courseResponse.data) ? courseResponse.data : (courseResponse.data?.items || [])
  } catch (e) { error.value = messageFrom(e, 'Não foi possível carregar o Certificate Studio.') }
  finally { loading.value = false }
}
async function createTemplate() {
  busy.value = true; clearMessages()
  try {
    const response = await createCertificateTemplate(newTemplate)
    templates.value.push(response.data)
    templates.value.sort((a, b) => a.name.localeCompare(b.name))
    newTemplate.name = ''; newTemplate.slug = ''; showCreate.value = false
    await selectTemplate(response.data)
    notice.value = 'Template criado. Crie e publique a primeira versão visual.'
  } catch (e) { error.value = messageFrom(e, 'Não foi possível criar o template.') }
  finally { busy.value = false }
}
async function selectTemplate(item) {
  selectedTemplate.value = item; selectedVersion.value = null; fillForm()
  try {
    versions.value = (await listCertificateTemplateVersions(item.id)).data
    if (versions.value.length) selectVersion(versions.value[0])
  } catch (e) { error.value = messageFrom(e, 'Não foi possível carregar as versões.') }
}
function selectVersion(version) { selectedVersion.value = version; fillForm(version.visual_config) }
async function createDraft() {
  busy.value = true; clearMessages()
  try {
    const response = await createCertificateTemplateVersion(selectedTemplate.value.id, selectedVersion.value?.visual_config || defaults())
    versions.value.unshift(response.data); selectVersion(response.data); notice.value = `Versão ${response.data.version} criada como rascunho.`
  } catch (e) { error.value = messageFrom(e, 'Não foi possível criar a versão.') }
  finally { busy.value = false }
}
async function saveDraft() {
  if (published.value) return
  busy.value = true; clearMessages()
  try {
    const response = await updateCertificateTemplateVersion(selectedTemplate.value.id, selectedVersion.value.id, { ...form })
    Object.assign(selectedVersion.value, response.data); notice.value = 'Rascunho salvo.'
  } catch (e) { error.value = messageFrom(e, 'Não foi possível salvar o rascunho.') }
  finally { busy.value = false }
}
async function publish() {
  busy.value = true; clearMessages()
  try {
    await saveDraft()
    if (error.value) return
    const response = await publishCertificateTemplateVersion(selectedTemplate.value.id, selectedVersion.value.id)
    Object.assign(selectedVersion.value, response.data); notice.value = `Versão ${response.data.version} publicada e imutável.`
  } catch (e) { error.value = messageFrom(e, 'Não foi possível publicar a versão.') }
  finally { busy.value = false }
}
async function preview() {
  clearMessages()
  try {
    const response = await previewCertificateTemplate({ ...form })
    const url = URL.createObjectURL(response.data)
    window.open(url, '_blank', 'noopener,noreferrer')
    window.setTimeout(() => URL.revokeObjectURL(url), 60000)
  } catch (e) { error.value = messageFrom(e, 'Não foi possível gerar a prévia.') }
}
async function toggleArchive() {
  busy.value = true; clearMessages()
  try {
    const response = await updateCertificateTemplate(selectedTemplate.value.id, { is_active: !selectedTemplate.value.is_active })
    Object.assign(selectedTemplate.value, response.data); notice.value = response.data.is_active ? 'Template reativado.' : 'Template arquivado.'
  } catch (e) { error.value = messageFrom(e, 'Não foi possível alterar o template.') }
  finally { busy.value = false }
}
function loadLogo(event, field) {
  const file = event.target.files?.[0]
  if (!file) { form[field] = null; return }
  if (file.size > 250 * 1024) { error.value = 'A logo deve ter no máximo 250 KiB.'; event.target.value = ''; return }
  const reader = new FileReader(); reader.onload = () => { form[field] = reader.result }; reader.readAsDataURL(file)
}
async function loadResolution() {
  resolution.value = null; assignmentTemplateId.value = ''
  if (!selectedCourseId.value) return
  try {
    const response = await getCertificateTemplateResolution(selectedCourseId.value)
    resolution.value = response.data; assignmentTemplateId.value = response.data.template_id || ''
  } catch (e) { error.value = messageFrom(e, 'Não foi possível resolver o template do curso.') }
}
async function saveAssignment() {
  if (!selectedCourseId.value) return
  if (!assignmentTemplateId.value) return resetAssignment()
  busy.value = true; clearMessages()
  try { await assignCertificateTemplate(selectedCourseId.value, assignmentTemplateId.value); await loadResolution(); notice.value = 'Template aplicado ao curso.' }
  catch (e) { error.value = messageFrom(e, 'Não foi possível aplicar o template. Publique uma versão antes de atribuí-lo.') }
  finally { busy.value = false }
}
async function resetAssignment() {
  if (!selectedCourseId.value) return
  busy.value = true; clearMessages()
  try { await resetCertificateTemplate(selectedCourseId.value); await loadResolution(); notice.value = 'Curso voltou ao template padrão do sistema.' }
  catch (e) { error.value = messageFrom(e, 'Não foi possível restaurar o padrão.') }
  finally { busy.value = false }
}

onMounted(load)
</script>
