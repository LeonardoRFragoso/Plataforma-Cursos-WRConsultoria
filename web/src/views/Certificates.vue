<template>
  <div>
    <!-- ════════════════════════════════════════════════════════════
         STUDENT CERTIFICATES — "Meus Certificados"
         ════════════════════════════════════════════════════════════ -->
    <template v-if="isStudent">
      <AppPageHeader
        title="Meus Certificados"
        description="Consulte e baixe os certificados conquistados nos seus cursos."
      />

      <!-- Loading -->
      <div v-if="loading" class="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div v-for="i in 2" :key="i" class="h-56 rounded-xl bg-gray-100 animate-pulse" />
      </div>

      <!-- Error -->
      <div
        v-else-if="loadError"
        class="rounded-xl border border-red-200 bg-red-50 p-6 text-center"
        data-testid="certificates-error"
      >
        <p class="text-red-700 mb-3">Não foi possível carregar seus certificados.</p>
        <button
          @click="loadMyCertificates"
          class="inline-flex items-center rounded-lg bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700"
        >
          Tentar novamente
        </button>
      </div>

      <!-- Empty -->
      <EmptyState
        v-else-if="myCertificates.length === 0"
        icon="🏆"
        title="Você ainda não possui certificados."
        description="Conclua os requisitos dos seus cursos para liberar seus certificados."
      >
        <router-link
          to="/dashboard"
          class="inline-flex items-center rounded-lg bg-primary-600 px-4 py-2 text-sm font-medium text-white hover:bg-primary-700"
        >
          Ver meus cursos
        </router-link>
      </EmptyState>

      <!-- Certificate grid -->
      <div v-else class="space-y-6">
        <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
          <CertificateCard
            v-for="cert in myCertificates"
            :key="cert.id"
            :certificate="cert"
            :test-id="'student-cert-' + cert.id"
          />
        </div>

        <!-- Subtle validation link -->
        <div class="text-center pt-2">
          <router-link
            to="/validar-certificado"
            class="text-sm text-gray-500 hover:text-primary-600 underline hover:no-underline"
          >
            Validar outro certificado →
          </router-link>
        </div>
      </div>
    </template>

    <!-- ════════════════════════════════════════════════════════════
         ADMIN CERTIFICATES — management tools
         ════════════════════════════════════════════════════════════ -->
    <template v-else-if="isAdmin">
      <AppPageHeader title="Certificados" description="Gerencie e valide certificados.">
        <template #actions>
          <AppButton
            @click="showForm = true"
            class="bg-primary-600 text-white"
            data-testid="new-certificate-btn"
          >
            + Novo Certificado
          </AppButton>
        </template>
      </AppPageHeader>

      <!-- Generate form -->
      <AppCard v-if="showForm" class="mb-8">
        <template #header>
          <h2 class="text-xl font-semibold text-secondary-900">Gerar Certificado</h2>
        </template>
        <form @submit.prevent="saveCertificate" class="space-y-4">
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">Matrícula Concluída *</label>
            <select
              v-model="form.enrollment_id"
              class="w-full px-4 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500"
              required
            >
              <option value="">Selecione uma matrícula</option>
              <option v-for="enrollment in completedEnrollments" :key="enrollment.id" :value="enrollment.id">
                {{ getStudentCpfById(enrollment.student_id) }} - {{ getClassNameById(enrollment.class_id) }}
              </option>
            </select>
          </div>
          <div class="flex gap-2">
            <AppButton type="submit" class="bg-primary-600 text-white" :disabled="saving" data-testid="generate-certificate-btn">
              {{ saving ? 'Gerando...' : 'Gerar' }}
            </AppButton>
            <AppButton type="button" @click="showForm = false" class="bg-gray-300 text-gray-700" data-testid="cancel-certificate-btn">Cancelar</AppButton>
          </div>
        </form>
      </AppCard>

      <!-- Validation -->
      <AppCard class="mb-8">
        <template #header>
          <h2 class="text-xl font-semibold text-secondary-900">Validar Certificado</h2>
        </template>
        <div class="flex gap-2">
          <AppInput
            v-model="validationCode"
            label="Código de Validação"
            placeholder="XXXX-XXXX-XXXX-XXXX"
            class="flex-1"
          />
          <AppButton @click="validateCertificate" class="bg-blue-600 text-white mt-auto" data-testid="validate-certificate-btn">Validar</AppButton>
        </div>
        <AppAlert
          v-if="validationError"
          type="error"
          class="mt-4"
          closable
          @close="validationError = ''"
        >
          {{ validationError }}
        </AppAlert>
        <div v-if="validationResult" class="mt-4 p-4 rounded" :class="validationResult.valid ? 'bg-green-50 border border-green-200 text-green-800' : 'bg-red-50 border border-red-200 text-red-800'">
          <p v-if="validationResult.valid">
            <strong>✓ Certificado válido</strong><br>
            Número: {{ validationResult.certificate_number }}<br>
            Aluno: {{ validationResult.student_name }}<br>
            Curso: {{ validationResult.course_name }}<br>
            Emitido em: {{ formatDate(validationResult.issued_at) }}
          </p>
          <p v-else>
            <strong>✗ Certificado inválido</strong>
          </p>
        </div>
      </AppCard>

      <!-- Admin list -->
      <LoadingState v-if="loading" message="Carregando certificados..." />
      <AppAlert
        v-else-if="loadError"
        type="error"
        class="mb-8"
        closable
        @close="loadError = ''"
      >
        {{ loadError }}
      </AppAlert>
      <EmptyState
        v-else-if="adminCertificates.length === 0"
        title="Nenhum certificado emitido"
        description="Certificados aparecerão aqui após a conclusão de cursos."
      />
      <div v-else class="grid grid-cols-1 md:grid-cols-2 gap-6">
        <AppCard v-for="cert in adminCertificates" :key="cert.id" class="hover:shadow-lg transition-shadow">
          <template #header>
            <h3 class="text-lg font-semibold text-secondary-900">{{ getStudentCpfByEnrollment(cert) }}</h3>
          </template>
          <div class="space-y-2 text-sm">
            <p><strong>Número:</strong> {{ cert.certificate_number }}</p>
            <p><strong>Código de Validação:</strong> <span class="font-mono bg-gray-100 px-2 py-1 rounded">{{ cert.validation_code }}</span></p>
            <p><strong>Curso:</strong> {{ getClassNameByEnrollment(cert.enrollment_id) }}</p>
            <p><strong>Emitido em:</strong> {{ formatDate(cert.issued_at) }}</p>
          </div>
          <div class="mt-4 flex gap-2">
            <AppButton @click="confirmDelete(cert)" class="bg-red-600 text-white text-sm flex-1" data-testid="delete-certificate-btn">Deletar</AppButton>
          </div>
        </AppCard>
      </div>

      <ConfirmDialog
        v-model="showDeleteConfirm"
        title="Excluir certificado"
        :message="deleteMessage"
        confirmText="Excluir"
        cancelText="Cancelar"
        :danger="true"
        :loading="deleting"
        @confirm="doDelete"
      />
    </template>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { useAuthStore } from '../stores/auth'
import api from '../api/client'
import { fetchMyCertificates } from '../api/certificates'
import AppPageHeader from '../components/AppPageHeader.vue'
import AppCard from '../components/AppCard.vue'
import AppButton from '../components/AppButton.vue'
import AppInput from '../components/AppInput.vue'
import AppAlert from '../components/AppAlert.vue'
import EmptyState from '../components/EmptyState.vue'
import LoadingState from '../components/LoadingState.vue'
import ConfirmDialog from '../components/ConfirmDialog.vue'
import CertificateCard from '../components/CertificateCard.vue'
import { useToast } from '../composables/useToast'

const { error: toastError } = useToast()
const authStore = useAuthStore()

const isAdmin = computed(() => authStore.userRole?.toLowerCase() === 'admin' || authStore.userRole?.toLowerCase() === 'super_admin')
const isStudent = computed(() => authStore.userRole?.toLowerCase() === 'student')

// ── Student certificates ──
const myCertificates = ref([])
const loading = ref(false)
const loadError = ref('')

const loadMyCertificates = async () => {
  loading.value = true
  loadError.value = ''
  try {
    const { data } = await fetchMyCertificates()
    myCertificates.value = data
  } catch (error) {
    console.error('Erro ao carregar certificados:', error)
    loadError.value = 'Não foi possível carregar seus certificados.'
  } finally {
    loading.value = false
  }
}

// ── Admin certificates ──
const adminCertificates = ref([])
const enrollments = ref([])
const students = ref([])
const classes = ref([])
const courses = ref([])
const showForm = ref(false)
const form = ref({ enrollment_id: '' })
const validationCode = ref('')
const validationResult = ref(null)
const showDeleteConfirm = ref(false)
const deleting = ref(false)
const pendingDeleteId = ref(null)
const pendingDeleteNumber = ref('')
const saving = ref(false)
const validationError = ref('')

const deleteMessage = computed(() =>
  `Excluir o certificado "${pendingDeleteNumber.value}"? Esta ação não pode ser desfeita.`
)

const completedEnrollments = computed(() =>
  enrollments.value.filter(e => e.status === 'CONCLUIDA')
)

const formatDate = (date) => new Date(date).toLocaleDateString('pt-BR')

const getStudentCpfById = (id) =>
  students.value.find(s => s.id === id)?.cpf || 'Aluno desconhecido'

const getCourseNameById = (id) =>
  courses.value.find(c => c.id === id)?.name || 'Curso desconhecido'

const getClassNameById = (classId) => {
  const cls = classes.value.find(c => c.id === classId)
  if (!cls) return 'Turma desconhecida'
  return `${getCourseNameById(cls.course_id)} - ${formatDate(cls.start_date)}`
}

const getStudentCpfByEnrollment = (cert) => {
  const enrollment = enrollments.value.find(e => e.id === cert.enrollment_id)
  if (!enrollment) return 'Desconhecido'
  return getStudentCpfById(enrollment.student_id)
}

const getClassNameByEnrollment = (enrollmentId) => {
  const enrollment = enrollments.value.find(e => e.id === enrollmentId)
  if (!enrollment) return 'Curso desconhecido'
  return getClassNameById(enrollment.class_id)
}

const loadAdminCertificates = async () => {
  loading.value = true
  loadError.value = ''
  try {
    const response = await api.get('/api/v1/certificates/')
    adminCertificates.value = response.data
  } catch (error) {
    console.error('Erro ao carregar certificados:', error)
    loadError.value = 'Erro ao carregar certificados. Tente novamente.'
  } finally {
    loading.value = false
  }
}

const loadDependencies = async () => {
  try {
    const [enrollmentsRes, studentsRes, classesRes, coursesRes] = await Promise.all([
      api.get('/api/v1/enrollments/'),
      api.get('/api/v1/students/'),
      api.get('/api/v1/classes/'),
      api.get('/api/v1/courses/')
    ])
    enrollments.value = enrollmentsRes.data
    students.value = studentsRes.data
    classes.value = classesRes.data
    courses.value = coursesRes.data
  } catch (error) {
    console.error('Erro ao carregar dependências:', error)
  }
}

const saveCertificate = async () => {
  saving.value = true
  try {
    await api.post('/api/v1/certificates/', form.value)
    form.value = { enrollment_id: '' }
    showForm.value = false
    loadAdminCertificates()
  } catch (error) {
    console.error('Erro ao gerar certificado:', error)
    toastError('Erro ao gerar certificado: ' + (error.response?.data?.detail || error.message))
  } finally {
    saving.value = false
  }
}

const validateCertificate = async () => {
  validationError.value = ''
  validationResult.value = null
  try {
    const response = await api.post('/api/v1/certificates/validate', { validation_code: validationCode.value })
    validationResult.value = response.data
  } catch (error) {
    console.error('Erro ao validar certificado:', error)
    if (error.response?.status === 404) {
      validationResult.value = { valid: false }
    } else {
      validationError.value = 'Erro ao validar certificado. Verifique sua conexão e tente novamente.'
    }
  }
}

const confirmDelete = (cert) => {
  pendingDeleteId.value = cert.id
  pendingDeleteNumber.value = cert.certificate_number
  showDeleteConfirm.value = true
}

const doDelete = async () => {
  deleting.value = true
  try {
    await api.delete(`/api/v1/certificates/${pendingDeleteId.value}`)
    showDeleteConfirm.value = false
    pendingDeleteId.value = null
    pendingDeleteNumber.value = ''
    loadAdminCertificates()
  } catch (error) {
    console.error('Erro ao deletar certificado:', error)
    toastError('Erro ao deletar certificado')
  } finally {
    deleting.value = false
  }
}

onMounted(async () => {
  await authStore.initializeUser()
  if (isStudent.value) {
    loadMyCertificates()
  } else if (isAdmin.value) {
    loadDependencies()
    loadAdminCertificates()
  }
})
</script>
