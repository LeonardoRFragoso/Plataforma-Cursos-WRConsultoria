<template>
  <div class="space-y-8">
    <!-- ════════════════════════════════════════════════════════════
         ADMIN DASHBOARD (unchanged IA)
         ════════════════════════════════════════════════════════════ -->
    <template v-if="isAdmin">
      <AppPageHeader title="Dashboard" description="Visão geral da sua plataforma." />

      <div class="mb-8">
        <div v-if="statsLoading" class="text-center py-4 text-gray-600" data-testid="dashboard-stats-loading">
          Carregando estatísticas...
        </div>
        <div v-else-if="statsError" class="bg-red-50 border border-red-200 text-red-700 p-4 rounded-md" data-testid="dashboard-stats-error">
          Erro ao carregar estatísticas: {{ statsError }}
          <button @click="loadStats" class="ml-2 underline hover:no-underline">Tentar novamente</button>
        </div>
        <div v-else class="grid grid-cols-1 md:grid-cols-4 gap-4">
          <AppCard>
            <div class="text-gray-600 text-sm">Total de Alunos</div>
            <div class="text-3xl font-bold text-primary-600">{{ stats.totalStudents }}</div>
          </AppCard>
          <AppCard>
            <div class="text-gray-600 text-sm">Turmas Ativas</div>
            <div class="text-3xl font-bold text-primary-600">{{ stats.activeClasses }}</div>
          </AppCard>
          <AppCard>
            <div class="text-gray-600 text-sm">Matrículas Pendentes</div>
            <div class="text-3xl font-bold text-primary-600">{{ stats.pendingEnrollments }}</div>
          </AppCard>
          <AppCard>
            <div class="text-gray-600 text-sm">Receita do Mês</div>
            <div class="text-3xl font-bold text-primary-600">R$ {{ stats.monthlyRevenue }}</div>
          </AppCard>
        </div>
      </div>

      <div class="grid grid-cols-1 md:grid-cols-3 gap-8">
        <AppCard>
          <template #header>
            <h3 class="text-xl font-semibold text-secondary-900">🔧 Gerenciamento</h3>
          </template>
          <div class="space-y-3">
            <AppLink to="/courses" class="block">📚 Cursos</AppLink>
            <AppLink to="/classes" class="block">👥 Turmas</AppLink>
            <AppLink to="/students" class="block">👤 Alunos</AppLink>
            <AppLink to="/enrollments" class="block">📝 Matrículas</AppLink>
            <AppLink to="/payments" class="block">💳 Pagamentos</AppLink>
          </div>
        </AppCard>
        <AppCard>
          <template #header>
            <h3 class="text-xl font-semibold text-secondary-900">🏆 Certificados</h3>
          </template>
          <AppLink to="/certificates">Ver certificados →</AppLink>
        </AppCard>
        <AppCard>
          <template #header>
            <h3 class="text-xl font-semibold text-secondary-900">ℹ️ Meu Perfil</h3>
          </template>
          <div class="space-y-2 text-sm">
            <p><strong>Função:</strong> {{ userRoleDisplay }}</p>
            <p v-if="authStore.loading"><strong>Nome:</strong> <span class="text-gray-400">Carregando…</span></p>
            <p v-else><strong>Nome:</strong> {{ authStore.user?.full_name || 'Não informado' }}</p>
            <p v-if="authStore.loading"><strong>E-mail:</strong> <span class="text-gray-400">Carregando…</span></p>
            <p v-else><strong>E-mail:</strong> {{ authStore.user?.email || 'Não informado' }}</p>
          </div>
        </AppCard>
      </div>
    </template>

    <!-- ════════════════════════════════════════════════════════════
         STUDENT DASHBOARD — learning-first experience
         ════════════════════════════════════════════════════════════ -->
    <template v-else-if="isStudent">
      <!-- Welcome -->
      <section class="rounded-2xl bg-gradient-to-br from-primary-600 to-primary-800 text-white p-6 sm:p-8 shadow-sm" data-testid="student-welcome">
        <h1 class="text-2xl sm:text-3xl font-bold">
          Olá, {{ firstName || 'aluno' }} <span class="inline-block animate-pulse">👋</span>
        </h1>
        <p class="mt-2 text-white/85">
          {{ welcomeSubtitle }}
        </p>
      </section>

      <!-- Summary metrics -->
      <section class="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4">
        <template v-if="loadingEnrollments">
          <div v-for="i in 4" :key="i" class="h-24 rounded-xl bg-gray-100 animate-pulse" />
        </template>
        <template v-else>
          <StudentMetricCard
            :value="metrics.total"
            label="Cursos matriculados"
            icon="📚"
            tone="primary"
            test-id="metric-enrolled"
          />
          <StudentMetricCard
            :value="metrics.inProgress"
            label="Em andamento"
            icon="▶"
            tone="primary"
            test-id="metric-in-progress"
          />
          <StudentMetricCard
            :value="metrics.completed"
            label="Concluídos"
            icon="✓"
            tone="success"
            test-id="metric-completed"
          />
          <StudentMetricCard
            :value="metrics.certificates"
            label="Certificados"
            icon="🏆"
            tone="accent"
            test-id="metric-certificates"
          />
        </template>
      </section>

      <!-- Error state -->
      <div
        v-if="enrollmentsError"
        class="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700"
        data-testid="dashboard-enrollments-error"
      >
        <p class="mb-2">{{ enrollmentsError }}</p>
        <button @click="loadMyEnrollments" class="underline hover:no-underline">Tentar novamente</button>
      </div>

      <!-- Main grid: Continue learning + sidebar -->
      <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <!-- Continue learning (2/3) -->
        <div class="lg:col-span-2 space-y-4">
          <SectionHeader
            title="Continue aprendendo"
            description="Retome de onde você parou."
          >
            <template #actions>
              <router-link
                to="/cursos"
                class="text-sm font-medium text-primary-600 hover:text-primary-700 whitespace-nowrap"
              >
                Explorar catálogo →
              </router-link>
            </template>
          </SectionHeader>

          <EmptyState
            v-if="!loadingEnrollments && myEnrollments.length === 0"
            icon="📚"
            title="Você ainda não está matriculado em nenhum curso."
            description="Explore nosso catálogo e comece sua jornada de aprendizado."
          >
            <AppLink to="/cursos" class="inline-flex items-center rounded-lg bg-primary-600 px-4 py-2 text-sm font-medium text-white hover:bg-primary-700">
              Explorar catálogo
            </AppLink>
          </EmptyState>

          <template v-else>
            <template v-if="loadingEnrollments">
              <div v-for="i in 2" :key="i" class="h-32 rounded-xl bg-gray-100 animate-pulse" />
            </template>
            <template v-else>
              <CourseProgressCard
                v-for="enrollment in playableEnrollments"
                :key="enrollment.id"
                :enrollment="enrollment"
                :certificate-course-ids="certificateCourseIds"
                :test-id="'progress-card-' + enrollment.course_id"
              />
              <!-- Pending enrollments (no CTA yet) -->
              <CourseProgressCard
                v-for="enrollment in pendingEnrollments"
                :key="enrollment.id"
                :enrollment="enrollment"
                :certificate-course-ids="certificateCourseIds"
                :test-id="'progress-card-pending-' + enrollment.course_id"
              />
            </template>
          </template>
        </div>

        <!-- Right column: Certificates + Profile (1/3) -->
        <div class="space-y-6">
          <!-- Certificates summary -->
          <div class="rounded-xl border border-gray-200 bg-white p-5 shadow-sm" data-testid="dashboard-cert-summary">
            <SectionHeader title="Certificados" />
            <template v-if="certificatesLoading">
              <div class="h-20 rounded-lg bg-gray-100 animate-pulse" />
            </template>
            <template v-else-if="myCertificates.length > 0">
              <div
                v-for="cert in latestCertificates"
                :key="cert.id"
                class="flex items-center gap-3 rounded-lg border border-gray-100 p-3 mb-2"
              >
                <span class="text-2xl" aria-hidden="true">🏆</span>
                <div class="min-w-0 flex-1">
                  <p class="font-medium text-secondary-900 truncate text-sm">{{ cert.course_name }}</p>
                  <p class="text-xs text-gray-500">Emitido em {{ formatDate(cert.issued_at) }}</p>
                </div>
              </div>
              <AppLink to="/certificates" class="block mt-3 text-sm font-medium text-primary-600 hover:text-primary-700">
                Ver todos →
              </AppLink>
            </template>
            <EmptyState
              v-else
              icon="🏆"
              title="Nenhum certificado ainda"
              description="Conclua seus cursos para conquistar certificados."
              :class_="'py-6'"
            />
          </div>

          <!-- Profile -->
          <StudentProfileCard
            :user="authStore.user"
            role="student"
          />
        </div>
      </div>

      <!-- Discover more -->
      <section v-if="!loadingEnrollments && myEnrollments.length > 0" class="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
        <SectionHeader
          title="Explore novos treinamentos"
          description="Descubra novos cursos para continuar sua jornada."
        >
          <template #actions>
            <router-link
              to="/cursos"
              class="inline-flex items-center rounded-lg bg-primary-600 px-4 py-2 text-sm font-medium text-white hover:bg-primary-700 whitespace-nowrap"
            >
              Explorar catálogo
            </router-link>
          </template>
        </SectionHeader>
      </section>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useAuthStore } from '../stores/auth'
import api from '../api/client'
import { fetchMyCertificates } from '../api/certificates'
import AppPageHeader from '../components/AppPageHeader.vue'
import AppCard from '../components/AppCard.vue'
import AppLink from '../components/AppLink.vue'
import StudentMetricCard from '../components/StudentMetricCard.vue'
import CourseProgressCard from '../components/CourseProgressCard.vue'
import StudentProfileCard from '../components/StudentProfileCard.vue'
import SectionHeader from '../components/SectionHeader.vue'
import EmptyState from '../components/EmptyState.vue'

const authStore = useAuthStore()

const roleMap = {
  'admin': 'Administrador',
  'student': 'Aluno',
  'super_admin': 'Super Administrador',
}

const userRoleDisplay = computed(() =>
  roleMap[authStore.userRole?.toLowerCase()] || authStore.userRole
)

const isAdmin = computed(() =>
  authStore.userRole?.toLowerCase() === 'admin' || authStore.userRole?.toLowerCase() === 'super_admin'
)
const isStudent = computed(() => authStore.userRole?.toLowerCase() === 'student')

// ── Admin stats ──
const stats = ref({ totalStudents: 0, activeClasses: 0, pendingEnrollments: 0, monthlyRevenue: 0 })
const statsLoading = ref(false)
const statsError = ref('')

// ── Student enrollments ──
const myEnrollments = ref([])
const loadingEnrollments = ref(false)
const enrollmentsError = ref('')

// ── Student certificates ──
const myCertificates = ref([])
const certificatesLoading = ref(false)

const firstName = computed(() => {
  const name = authStore.user?.full_name || ''
  return name.trim().split(/\s+/)[0] || ''
})

const playableEnrollments = computed(() =>
  myEnrollments.value.filter(e => e.status === 'CONFIRMADA' || e.status === 'CONCLUIDA')
)

const pendingEnrollments = computed(() =>
  myEnrollments.value.filter(e => e.status === 'PENDENTE' || e.status === 'CANCELADA')
)

const certificateCourseIds = computed(
  () => new Set(myCertificates.value.map(c => c.course_id))
)

const metrics = computed(() => {
  const total = myEnrollments.value.length
  const completed = myEnrollments.value.filter(e => e.status === 'CONCLUIDA').length
  const inProgress = total - completed - myEnrollments.value.filter(e => e.status === 'PENDENTE' || e.status === 'CANCELADA').length
  return {
    total,
    inProgress: Math.max(0, inProgress),
    completed,
    certificates: myCertificates.value.length,
  }
})

const welcomeSubtitle = computed(() => {
  const m = metrics.value
  if (m.total === 0) return 'Explore nosso catálogo e comece sua jornada de aprendizado.'
  if (m.inProgress > 0) return `Você tem ${m.inProgress} curso${m.inProgress > 1 ? 's' : ''} em andamento.`
  if (m.completed > 0) return `Parabéns! Você concluiu ${m.completed} curso${m.completed > 1 ? 's' : ''}.`
  return 'Continue sua jornada de aprendizado.'
})

const latestCertificates = computed(() => myCertificates.value.slice(0, 2))

const formatDate = (date) => new Date(date).toLocaleDateString('pt-BR')

const loadMyEnrollments = async () => {
  if (!isStudent.value) return
  loadingEnrollments.value = true
  enrollmentsError.value = ''
  try {
    const response = await api.get('/api/v1/enrollments/me')
    myEnrollments.value = response.data
  } catch (error) {
    console.error('Erro ao carregar matrículas:', error)
    enrollmentsError.value = error.response?.data?.detail || 'Não foi possível carregar suas matrículas.'
  } finally {
    loadingEnrollments.value = false
  }
}

const loadMyCertificates = async () => {
  if (!isStudent.value) return
  certificatesLoading.value = true
  try {
    const { data } = await fetchMyCertificates()
    myCertificates.value = data
  } catch (error) {
    console.error('Erro ao carregar certificados:', error)
    myCertificates.value = []
  } finally {
    certificatesLoading.value = false
  }
}

const loadStats = async () => {
  if (!isAdmin.value) return
  statsLoading.value = true
  statsError.value = ''
  try {
    const response = await api.get('/api/v1/dashboard/stats')
    stats.value = response.data
  } catch (error) {
    console.error('Erro ao carregar estatísticas:', error)
    statsError.value = error.response?.data?.detail || 'Não foi possível carregar as estatísticas.'
  } finally {
    statsLoading.value = false
  }
}

onMounted(async () => {
  await authStore.initializeUser()
  await Promise.all([loadStats(), loadMyEnrollments(), loadMyCertificates()])
})
</script>
