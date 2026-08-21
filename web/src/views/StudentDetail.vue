<template>
  <div>
    <!-- Back -->
    <button @click="$router.push('/students')" class="text-sm text-gray-600 hover:text-gray-900 mb-4">
      ← Voltar para Alunos
    </button>

    <LoadingState v-if="loading" message="Carregando aluno..." />

    <template v-else-if="student">
      <!-- Header -->
      <div class="flex items-start justify-between mb-6">
        <div>
          <h1 class="text-2xl font-bold text-secondary-900">{{ student.full_name }}</h1>
          <p class="text-sm text-gray-600">{{ student.email }}</p>
          <div class="flex items-center gap-3 mt-2">
            <span class="text-sm text-gray-500">CPF: {{ student.cpf }}</span>
            <span
              :class="student.company_id ? 'bg-blue-100 text-blue-800' : 'bg-gray-100 text-gray-700'"
              class="px-2 py-0.5 rounded text-xs font-medium"
            >
              {{ student.company_id ? 'Corporativo' : 'Individual' }}
            </span>
          </div>
          <div v-if="student.company_id" class="text-sm text-gray-600 mt-1">
            Funcionário de:
            <router-link :to="`/companies/${student.company_id}`" class="text-primary-600 hover:underline font-medium">
              {{ getCompanyName(student.company_id) }}
            </router-link>
          </div>
          <div v-else class="text-sm text-gray-500 mt-1">Aluno independente</div>
        </div>
      </div>

      <!-- Info Cards -->
      <div class="grid grid-cols-1 md:grid-cols-2 gap-4 mb-8">
        <AppCard>
          <template #header><h3 class="text-sm font-semibold text-gray-700">Dados Pessoais</h3></template>
          <dl class="space-y-2 text-sm">
            <div><dt class="inline text-gray-500">Telefone:</dt> <dd class="inline text-gray-900">{{ student.phone || '—' }}</dd></div>
            <div><dt class="inline text-gray-500">Cidade:</dt> <dd class="inline text-gray-900">{{ student.city || '—' }}</dd></div>
            <div><dt class="inline text-gray-500">Estado:</dt> <dd class="inline text-gray-900">{{ student.state || '—' }}</dd></div>
            <div><dt class="inline text-gray-500">Endereço:</dt> <dd class="inline text-gray-900">{{ student.address || '—' }}</dd></div>
            <div><dt class="inline text-gray-500">CEP:</dt> <dd class="inline text-gray-900">{{ student.zip_code || '—' }}</dd></div>
          </dl>
        </AppCard>

        <AppCard>
          <template #header><h3 class="text-sm font-semibold text-gray-700">Resumo</h3></template>
          <div class="grid grid-cols-3 gap-3 text-center">
            <div>
              <div class="text-2xl font-bold text-primary-600">{{ studentEnrollments.length }}</div>
              <div class="text-xs text-gray-500">Matrículas</div>
            </div>
            <div>
              <div class="text-2xl font-bold text-green-600">{{ completedCount }}</div>
              <div class="text-xs text-gray-500">Concluídos</div>
            </div>
            <div>
              <div class="text-2xl font-bold text-indigo-600">{{ certificateCount }}</div>
              <div class="text-xs text-gray-500">Certificados</div>
            </div>
          </div>
        </AppCard>
      </div>

      <!-- Enrollments -->
      <AppCard class="mb-8">
        <template #header><h3 class="text-lg font-semibold text-secondary-900">Matrículas</h3></template>

        <EmptyState
          v-if="studentEnrollments.length === 0"
          title="Nenhuma matrícula"
          description="Este aluno ainda não foi matriculado em nenhum curso."
        />

        <div v-else class="overflow-x-auto">
          <table class="w-full border-collapse">
            <thead>
              <tr class="bg-gray-100">
                <th class="px-3 py-2 text-left text-sm font-semibold text-gray-700">Curso</th>
                <th class="px-3 py-2 text-left text-sm font-semibold text-gray-700">Turma</th>
                <th class="px-3 py-2 text-left text-sm font-semibold text-gray-700">Status</th>
                <th class="px-3 py-2 text-left text-sm font-semibold text-gray-700">Origem</th>
                <th class="px-3 py-2 text-left text-sm font-semibold text-gray-700">Valor</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="enr in studentEnrollments" :key="enr.id" class="border-b hover:bg-gray-50">
                <td class="px-3 py-2 text-sm">{{ getCourseNameByClassId(enr.class_id) }}</td>
                <td class="px-3 py-2 text-sm text-gray-600">{{ getClassLabel(enr.class_id) }}</td>
                <td class="px-3 py-2"><StatusBadge :status="enr.status" /></td>
                <td class="px-3 py-2">
                  <span :class="enr.source === 'CORPORATE' ? 'bg-blue-100 text-blue-800' : 'bg-gray-100 text-gray-700'" class="px-2 py-0.5 rounded text-xs font-medium">
                    {{ enr.source === 'CORPORATE' ? 'Corporativo' : 'Individual' }}
                  </span>
                </td>
                <td class="px-3 py-2 text-sm text-gray-600">R$ {{ enr.price?.toFixed(2) || '0,00' }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </AppCard>

      <!-- Certificates -->
      <AppCard>
        <template #header><h3 class="text-lg font-semibold text-secondary-900">Certificados</h3></template>

        <EmptyState
          v-if="certificates.length === 0"
          title="Nenhum certificado emitido"
          description="Certificados serão emitidos automaticamente ao concluir cursos."
        />

        <div v-else class="space-y-3">
          <CertificateCard v-for="cert in certificates" :key="cert.id" :certificate="cert" />
        </div>
      </AppCard>
    </template>

    <EmptyState v-else title="Aluno não encontrado" description="O aluno solicitado não existe ou foi removido." />
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { useRoute } from 'vue-router'
import api from '../api/client'
import AppCard from '../components/AppCard.vue'
import EmptyState from '../components/EmptyState.vue'
import LoadingState from '../components/LoadingState.vue'
import StatusBadge from '../components/StatusBadge.vue'
import CertificateCard from '../components/CertificateCard.vue'
import { useToast } from '../composables/useToast'

const { error: toastError } = useToast()
const route = useRoute()
const studentId = route.params.id

const student = ref(null)
const enrollments = ref([])
const certificates = ref([])
const classes = ref([])
const courses = ref([])
const companies = ref([])
const loading = ref(true)

const studentEnrollments = computed(() =>
  enrollments.value.filter(e => e.student_id === studentId)
)

const completedCount = computed(() =>
  studentEnrollments.value.filter(e => e.status === 'CONCLUIDA').length
)

const certificateCount = computed(() => certificates.value.length)

const getCompanyName = (companyId) => {
  if (!companyId) return null
  return companies.value.find(c => c.id === companyId)?.trade_name || companies.value.find(c => c.id === companyId)?.legal_name
}

const getCourseNameByClassId = (classId) => {
  const cls = classes.value.find(c => c.id === classId)
  if (!cls) return '—'
  const course = courses.value.find(c => c.id === cls.course_id)
  return course ? course.name : '—'
}

const getClassLabel = (classId) => {
  const cls = classes.value.find(c => c.id === classId)
  if (!cls) return '—'
  return `${new Date(cls.start_date).toLocaleDateString('pt-BR')}`
}

const loadData = async () => {
  loading.value = true
  try {
    const [studentRes, enrollRes, certRes, classesRes, coursesRes, companiesRes] = await Promise.all([
      api.get(`/api/v1/students/${studentId}`),
      api.get('/api/v1/enrollments/'),
      api.get('/api/v1/certificates/'),
      api.get('/api/v1/classes/'),
      api.get('/api/v1/courses/'),
      api.get('/api/v1/companies/'),
    ])
    student.value = studentRes.data
    enrollments.value = enrollRes.data
    // Filter certificates for this student's enrollments
    const enrIds = new Set(studentEnrollments.value.map(e => e.id))
    certificates.value = certRes.data.filter(c => enrIds.has(c.enrollment_id))
    classes.value = classesRes.data
    courses.value = coursesRes.data
    companies.value = companiesRes.data
  } catch (error) {
    toastError('Erro ao carregar dados do aluno')
  } finally {
    loading.value = false
  }
}

onMounted(loadData)
</script>
