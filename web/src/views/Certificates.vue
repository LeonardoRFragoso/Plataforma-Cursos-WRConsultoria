<template>
  <div class="min-h-screen bg-gray-50">
    <AppNavbar />

    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div class="flex justify-between items-center mb-8">
        <h1 class="text-3xl font-bold text-secondary-900">Certificados</h1>
        <AppButton
          v-if="isAdmin"
          @click="showForm = true"
          class="bg-primary-600 text-white"
        >
          + Novo Certificado
        </AppButton>
      </div>

      <!-- Formulário -->
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
            <AppButton type="submit" class="bg-primary-600 text-white">Gerar</AppButton>
            <AppButton type="button" @click="showForm = false" class="bg-gray-300 text-gray-700">Cancelar</AppButton>
          </div>
        </form>
      </AppCard>

      <!-- Validação -->
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
          <AppButton @click="validateCertificate" class="bg-blue-600 text-white mt-auto">Validar</AppButton>
        </div>
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

      <!-- Lista -->
      <div v-if="loading" class="text-center py-8">
        <p class="text-gray-600">Carregando certificados...</p>
      </div>

      <div v-else-if="certificates.length === 0" class="text-center py-8">
        <p class="text-gray-600">Nenhum certificado emitido</p>
      </div>

      <div v-else class="grid grid-cols-1 md:grid-cols-2 gap-6">
        <AppCard v-for="cert in certificates" :key="cert.id" class="hover:shadow-lg transition-shadow">
          <template #header>
            <h3 class="text-lg font-semibold text-secondary-900">{{ getStudentCpfByPayment(cert) }}</h3>
          </template>
          <div class="space-y-2 text-sm">
            <p><strong>Número:</strong> {{ cert.certificate_number }}</p>
            <p><strong>Código de Validação:</strong> <span class="font-mono bg-gray-100 px-2 py-1 rounded">{{ cert.validation_code }}</span></p>
            <p><strong>Curso:</strong> {{ getClassNameByEnrollment(cert.enrollment_id) }}</p>
            <p><strong>Emitido em:</strong> {{ formatDate(cert.issued_at) }}</p>
          </div>
          <div v-if="isAdmin" class="mt-4 flex gap-2">
            <AppButton @click="deleteCertificate(cert.id)" class="bg-red-600 text-white text-sm flex-1">Deletar</AppButton>
          </div>
        </AppCard>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { useAuthStore } from '../stores/auth'
import api from '../api/client'
import AppNavbar from '../components/AppNavbar.vue'
import AppCard from '../components/AppCard.vue'
import AppButton from '../components/AppButton.vue'
import AppInput from '../components/AppInput.vue'

const authStore = useAuthStore()

const certificates = ref([])
const enrollments = ref([])
const students = ref([])
const classes = ref([])
const courses = ref([])
const loading = ref(false)
const showForm = ref(false)
const form = ref({
  enrollment_id: '',
})
const validationCode = ref('')
const validationResult = ref(null)

const isAdmin = computed(() => authStore.userRole?.toLowerCase() === 'admin' || authStore.userRole?.toLowerCase() === 'super_admin')

const completedEnrollments = computed(() => {
  return enrollments.value.filter(e => e.status === 'CONCLUIDA')
})

const formatDate = (date) => {
  return new Date(date).toLocaleDateString('pt-BR')
}

const getStudentCpfById = (id) => {
  return students.value.find(s => s.id === id)?.cpf || 'Aluno desconhecido'
}

const getCourseNameById = (id) => {
  return courses.value.find(c => c.id === id)?.name || 'Curso desconhecido'
}

const getClassNameById = (classId) => {
  const cls = classes.value.find(c => c.id === classId)
  if (!cls) return 'Turma desconhecida'
  return `${getCourseNameById(cls.course_id)} - ${formatDate(cls.start_date)}`
}

const getStudentCpfByPayment = (cert) => {
  const enrollment = enrollments.value.find(e => e.id === cert.enrollment_id)
  if (!enrollment) return 'Desconhecido'
  return getStudentCpfById(enrollment.student_id)
}

const getClassNameByEnrollment = (enrollmentId) => {
  const enrollment = enrollments.value.find(e => e.id === enrollmentId)
  if (!enrollment) return 'Curso desconhecido'
  return getClassNameById(enrollment.class_id)
}

const loadCertificates = async () => {
  loading.value = true
  try {
    const response = await api.get('/api/v1/certificates/')
    certificates.value = response.data
  } catch (error) {
    console.error('Erro ao carregar certificados:', error)
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
  try {
    await api.post('/api/v1/certificates/', form.value)
    resetForm()
    loadCertificates()
  } catch (error) {
    console.error('Erro ao gerar certificado:', error)
    alert('Erro ao gerar certificado: ' + (error.response?.data?.detail || error.message))
  }
}

const validateCertificate = async () => {
  try {
    const response = await api.post('/api/v1/certificates/validate', { validation_code: validationCode.value })
    validationResult.value = response.data
  } catch (error) {
    console.error('Erro ao validar certificado:', error)
    validationResult.value = { valid: false }
  }
}

const deleteCertificate = async (id) => {
  if (confirm('Tem certeza que deseja deletar este certificado?')) {
    try {
      await api.delete(`/api/v1/certificates/${id}`)
      loadCertificates()
    } catch (error) {
      console.error('Erro ao deletar certificado:', error)
      alert('Erro ao deletar certificado')
    }
  }
}

const resetForm = () => {
  form.value = { enrollment_id: '' }
  showForm.value = false
}

onMounted(() => {
  loadDependencies()
  loadCertificates()
})
</script>
