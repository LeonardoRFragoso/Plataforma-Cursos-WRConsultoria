<template>
  <div class="space-y-7">
    <AppPageHeader
      eyebrow="Compliance NR"
      title="Operação e auditoria"
      description="Acompanhe revisões regulatórias, jornada de conclusão, assinatura digital, integridade do ledger e governança de retenção."
    />

    <div v-if="error" class="rounded-2xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">{{ error }}</div>
    <div v-if="notice" class="rounded-2xl border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-800">{{ notice }}</div>

    <div v-if="loading" class="grid grid-cols-2 gap-4 xl:grid-cols-6">
      <div v-for="i in 6" :key="i" class="h-28 animate-pulse rounded-2xl bg-white/70"></div>
    </div>
    <template v-else>
      <section class="grid grid-cols-2 gap-3 sm:gap-4 xl:grid-cols-6">
        <OperationsMetric label="Revisões vencidas" :value="summary.reviews_expired || 0" icon="shield" />
        <OperationsMetric label="Revisões em 30 dias" :value="summary.reviews_due_30_days || 0" icon="calendar" />
        <OperationsMetric label="Matrículas sem ledger" :value="summary.enrollments_without_ledger_events || 0" icon="clipboard" />
        <OperationsMetric label="Assinaturas falhas" :value="summary.signing_job_status_counts?.FAILED || 0" icon="alert" />
        <OperationsMetric label="Aguardando assinatura" :value="pendingSignatures" icon="cert" />
        <OperationsMetric label="Política de retenção" :value="summary.retention_policy_ready ? `v${summary.approved_retention_policy_version}` : 'Pendente'" icon="archive" />
      </section>

      <section class="grid gap-5 xl:grid-cols-3">
        <div class="premium-card p-5 sm:p-6">
          <p class="premium-kicker">Cursos</p>
          <h2 class="mt-1 font-bold text-slate-900">Estado regulatório</h2>
          <div class="mt-4 space-y-2">
            <StatusRow v-for="(value, key) in summary.course_status_counts" :key="key" :label="key" :value="value" />
            <p v-if="!Object.keys(summary.course_status_counts || {}).length" class="text-sm text-slate-400">Nenhum perfil regulatório.</p>
          </div>
        </div>
        <div class="premium-card p-5 sm:p-6">
          <p class="premium-kicker">Matrículas</p>
          <h2 class="mt-1 font-bold text-slate-900">State machine</h2>
          <div class="mt-4 max-h-72 space-y-2 overflow-auto pr-1">
            <StatusRow v-for="(value, key) in summary.enrollment_state_counts" :key="key" :label="key" :value="value" />
            <p v-if="!Object.keys(summary.enrollment_state_counts || {}).length" class="text-sm text-slate-400">Nenhuma matrícula regulatória materializada.</p>
          </div>
        </div>
        <div class="premium-card p-5 sm:p-6">
          <p class="premium-kicker">Assinatura</p>
          <h2 class="mt-1 font-bold text-slate-900">PAdES / provedor</h2>
          <div class="mt-4 space-y-2">
            <StatusRow v-for="(value, key) in summary.signing_job_status_counts" :key="key" :label="key" :value="value" />
          </div>
          <div class="mt-4 rounded-2xl bg-slate-50 p-4 text-xs leading-5 text-slate-600">
            Perfil: <b>{{ summary.signer_profile_enabled ? 'habilitado' : 'desabilitado' }}</b><br />
            Certificado: <b>{{ signerState }}</b><br />
            Validade pública conhecida: {{ date(summary.signer_certificate_not_after) }}
          </div>
        </div>
      </section>

      <section class="premium-card p-5 sm:p-6">
        <div class="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p class="premium-kicker">Relatório por turma</p>
            <h2 class="mt-1 font-bold text-slate-900">Conformidade operacional</h2>
            <p class="mt-1 text-xs text-slate-400">A leitura é auditada e não altera nenhuma evidência.</p>
          </div>
          <div class="flex w-full max-w-xl gap-2">
            <select v-model="selectedClassId" class="min-w-0 flex-1 text-sm">
              <option value="">Selecione uma turma</option>
              <option v-for="item in classes" :key="item.id" :value="item.id">{{ item.description || item.id }} · {{ item.start_date }} → {{ item.end_date }}</option>
            </select>
            <button :disabled="busy || !selectedClassId" class="rounded-xl px-4 py-2 text-xs font-bold text-white disabled:opacity-40" :style="{ background: 'var(--brand-primary)' }" @click="loadClassReport">Gerar</button>
          </div>
        </div>
        <div v-if="classReport" class="mt-5 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          <div class="rounded-2xl bg-slate-50 p-4"><p class="text-xs font-bold text-slate-400">Curso</p><p class="mt-1 font-bold text-slate-800">{{ classReport.course_code }} — {{ classReport.course_name }}</p><p class="mt-1 text-xs text-slate-500">{{ classReport.regulatory_standard }} · {{ classReport.regulatory_version }}</p></div>
          <div class="rounded-2xl bg-slate-50 p-4"><p class="text-xs font-bold text-slate-400">Matrículas</p><p class="mt-1 text-2xl font-bold text-slate-800">{{ classReport.enrollment_count }}</p><p class="mt-1 text-xs text-slate-500">{{ classReport.training_event_count }} eventos de treinamento</p></div>
          <div class="rounded-2xl bg-slate-50 p-4"><p class="text-xs font-bold text-slate-400">Estados</p><p v-for="(v, k) in classReport.enrollment_state_counts" :key="k" class="mt-1 text-xs text-slate-600">{{ k }}: <b>{{ v }}</b></p></div>
          <div class="rounded-2xl bg-slate-50 p-4"><p class="text-xs font-bold text-slate-400">Certificados / assinatura</p><p v-for="(v, k) in classReport.certificate_status_counts" :key="`c-${k}`" class="mt-1 text-xs text-slate-600">{{ k }}: <b>{{ v }}</b></p><p v-for="(v, k) in classReport.signing_job_status_counts" :key="`s-${k}`" class="mt-1 text-xs text-slate-600">SIGN {{ k }}: <b>{{ v }}</b></p></div>
        </div>
      </section>

      <section class="premium-card p-5 sm:p-6">
        <div class="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <p class="premium-kicker">LGPD / retenção</p>
            <h2 class="mt-1 font-bold text-slate-900">Política versionada</h2>
            <p class="mt-1 max-w-3xl text-xs leading-5 text-slate-400">A plataforma não define prazos legais automaticamente e não possui purge automático. Uma versão só pode ser aprovada depois que todos os prazos, finalidade e base legal forem informados explicitamente.</p>
          </div>
          <button :disabled="busy" class="rounded-xl border border-slate-200 bg-white px-4 py-2 text-xs font-bold text-slate-700 disabled:opacity-40" @click="newRetentionDraft">Nova versão</button>
        </div>

        <div class="mt-5 grid gap-5 xl:grid-cols-[260px_minmax(0,1fr)]">
          <div class="space-y-2">
            <button v-for="item in retentionVersions" :key="item.id" class="w-full rounded-xl border p-3 text-left" :class="selectedRetention?.id === item.id ? 'border-emerald-300 bg-emerald-50' : 'border-slate-200 bg-white'" @click="selectRetention(item)">
              <div class="flex justify-between gap-2"><b class="text-sm text-slate-800">Versão {{ item.version }}</b><span class="rounded-full px-2 py-1 text-[10px] font-bold" :class="item.status === 'APPROVED' ? 'bg-emerald-100 text-emerald-700' : 'bg-amber-100 text-amber-700'">{{ item.status }}</span></div>
              <p class="mt-1 text-[11px] text-slate-400">Criada em {{ date(item.created_at) }}</p>
            </button>
            <p v-if="!retentionVersions.length" class="text-sm text-slate-400">Nenhuma política registrada.</p>
          </div>

          <form v-if="selectedRetention" class="space-y-4" @submit.prevent="saveRetention">
            <div class="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
              <RetentionInput v-model="retentionForm.certificate_retention_days" label="Certificados" :disabled="retentionApproved" />
              <RetentionInput v-model="retentionForm.assessment_retention_days" label="Avaliações" :disabled="retentionApproved" />
              <RetentionInput v-model="retentionForm.training_event_retention_days" label="Logs" :disabled="retentionApproved" />
              <RetentionInput v-model="retentionForm.student_confirmation_retention_days" label="Confirmação" :disabled="retentionApproved" />
              <RetentionInput v-model="retentionForm.practical_evidence_retention_days" label="Prática" :disabled="retentionApproved" />
            </div>
            <div class="grid gap-4 lg:grid-cols-2">
              <label class="text-xs font-bold text-slate-600">Base legal<textarea v-model.trim="retentionForm.legal_basis" :disabled="retentionApproved" rows="4" class="mt-1 w-full text-sm" placeholder="Preencher após validação jurídica/técnica" /></label>
              <label class="text-xs font-bold text-slate-600">Finalidade<textarea v-model.trim="retentionForm.purpose" :disabled="retentionApproved" rows="4" class="mt-1 w-full text-sm" placeholder="Finalidade documentada da retenção" /></label>
            </div>
            <label class="block text-xs font-bold text-slate-600">Notas<textarea v-model.trim="retentionForm.notes" :disabled="retentionApproved" rows="2" class="mt-1 w-full text-sm" /></label>
            <div class="flex flex-wrap justify-end gap-2 border-t border-slate-100 pt-4">
              <button v-if="!retentionApproved" :disabled="busy" class="rounded-xl border border-slate-200 bg-white px-4 py-2 text-xs font-bold text-slate-700 disabled:opacity-40">Salvar rascunho</button>
              <button v-if="!retentionApproved" type="button" :disabled="busy" class="rounded-xl px-4 py-2 text-xs font-bold text-white disabled:opacity-40" :style="{ background: 'var(--brand-primary)' }" @click="approveRetention">Aprovar versão</button>
            </div>
          </form>
        </div>
      </section>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import api from '../api/client'
import AppPageHeader from '../components/AppPageHeader.vue'
import OperationsMetric from '../components/OperationsMetric.vue'
import StatusRow from '../components/OperationsStatusRow.vue'
import RetentionInput from '../components/RetentionDaysInput.vue'
import {
  approveRetentionPolicyVersion,
  createRetentionPolicyVersion,
  getComplianceClassReport,
  getComplianceOperationsSummary,
  listRetentionPolicyVersions,
  updateRetentionPolicyVersion,
} from '../api/complianceOperations'

const summary = ref({ course_status_counts: {}, enrollment_state_counts: {}, signing_job_status_counts: {} })
const classes = ref([])
const classReport = ref(null)
const selectedClassId = ref('')
const retentionVersions = ref([])
const selectedRetention = ref(null)
const loading = ref(true)
const busy = ref(false)
const error = ref('')
const notice = ref('')
const retentionForm = reactive({})
const retentionApproved = computed(() => selectedRetention.value?.status === 'APPROVED')
const pendingSignatures = computed(() => ['QUEUED', 'SUBMITTING', 'WAITING_PROVIDER', 'RETRY_SCHEDULED'].reduce((sum, key) => sum + Number(summary.value.signing_job_status_counts?.[key] || 0), 0))
const signerState = computed(() => summary.value.signer_certificate_expired ? 'expirado' : summary.value.signer_certificate_expires_30_days ? 'vence em até 30 dias' : 'sem alerta de expiração')
const date = (value) => value ? new Date(value).toLocaleDateString('pt-BR') : '—'
const detail = (err, fallback) => typeof err?.response?.data?.detail === 'string' ? err.response.data.detail : fallback

function clearMessages() { error.value = ''; notice.value = '' }
function selectRetention(item) { selectedRetention.value = item; Object.assign(retentionForm, item) }
async function reloadSummary() { summary.value = (await getComplianceOperationsSummary()).data }
async function reloadRetention() {
  retentionVersions.value = (await listRetentionPolicyVersions()).data
  if (selectedRetention.value) {
    const current = retentionVersions.value.find((item) => item.id === selectedRetention.value.id)
    if (current) selectRetention(current)
  }
}
async function load() {
  loading.value = true
  try {
    const [summaryResponse, retentionResponse, classResponse] = await Promise.all([
      getComplianceOperationsSummary(),
      listRetentionPolicyVersions(),
      api.get('/api/v1/classes/'),
    ])
    summary.value = summaryResponse.data
    retentionVersions.value = retentionResponse.data
    classes.value = Array.isArray(classResponse.data) ? classResponse.data : (classResponse.data?.items || [])
    if (retentionVersions.value.length) selectRetention(retentionVersions.value[0])
  } catch (err) { error.value = detail(err, 'Não foi possível carregar a operação de compliance.') }
  finally { loading.value = false }
}
async function loadClassReport() {
  if (!selectedClassId.value) return
  busy.value = true; clearMessages()
  try { classReport.value = (await getComplianceClassReport(selectedClassId.value)).data }
  catch (err) { error.value = detail(err, 'Não foi possível gerar o relatório da turma.') }
  finally { busy.value = false }
}
async function newRetentionDraft() {
  busy.value = true; clearMessages()
  try {
    const response = await createRetentionPolicyVersion({})
    retentionVersions.value.unshift(response.data)
    selectRetention(response.data)
    notice.value = 'Nova política criada como rascunho. Nenhum prazo foi presumido.'
  } catch (err) { error.value = detail(err, 'Não foi possível criar a política.') }
  finally { busy.value = false }
}
function retentionPayload() {
  const numeric = ['certificate_retention_days', 'assessment_retention_days', 'training_event_retention_days', 'student_confirmation_retention_days', 'practical_evidence_retention_days']
  const payload = { legal_basis: retentionForm.legal_basis || null, purpose: retentionForm.purpose || null, notes: retentionForm.notes || null }
  numeric.forEach((key) => { payload[key] = retentionForm[key] ? Number(retentionForm[key]) : null })
  return payload
}
async function saveRetention() {
  if (!selectedRetention.value || retentionApproved.value) return
  busy.value = true; clearMessages()
  try {
    const response = await updateRetentionPolicyVersion(selectedRetention.value.id, retentionPayload())
    Object.assign(selectedRetention.value, response.data)
    notice.value = 'Rascunho salvo. Nenhuma exclusão automática foi habilitada.'
  } catch (err) { error.value = detail(err, 'Não foi possível salvar a política.') }
  finally { busy.value = false }
}
async function approveRetention() {
  if (!selectedRetention.value || retentionApproved.value) return
  await saveRetention()
  if (error.value) return
  busy.value = true; clearMessages()
  try {
    const response = await approveRetentionPolicyVersion(selectedRetention.value.id)
    Object.assign(selectedRetention.value, response.data)
    await Promise.all([reloadSummary(), reloadRetention()])
    notice.value = 'Política aprovada e congelada. O sistema continua sem purge automático.'
  } catch (err) {
    const responseDetail = err?.response?.data?.detail
    error.value = responseDetail?.missing ? `Preencha antes da aprovação: ${responseDetail.missing.join(', ')}.` : detail(err, 'Não foi possível aprovar a política.')
  } finally { busy.value = false }
}

onMounted(load)
</script>
