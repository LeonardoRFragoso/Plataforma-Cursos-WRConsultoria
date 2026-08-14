<template>
  <div class="min-h-screen bg-gray-50">
    <AppNavbar />

    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <h1 class="text-3xl font-bold text-secondary-900 mb-8">Dashboard</h1>

      <!-- Stats para ADMIN -->
      <div v-if="isAdmin" class="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
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

      <!-- Conteúdo por Role -->
      <div class="grid grid-cols-1 md:grid-cols-3 gap-8">
        <!-- Card de Gerenciamento (apenas ADMIN) -->
        <AppCard v-if="isAdmin">
          <template #header>
            <h3 class="text-xl font-semibold text-secondary-900">🔧 Gerenciamento</h3>
          </template>
          <div class="space-y-3">
            <AppLink to="/courses" class="block">
              📚 Cursos
            </AppLink>
            <AppLink to="/classes" class="block">
              👥 Turmas
            </AppLink>
            <AppLink to="/students" class="block">
              👤 Alunos
            </AppLink>
            <AppLink to="/enrollments" class="block">
              📝 Matrículas
            </AppLink>
            <AppLink to="/payments" class="block">
              💳 Pagamentos
            </AppLink>
          </div>
        </AppCard>

        <!-- Card de Cursos do Aluno (STUDENT) -->
        <AppCard v-if="isStudent">
          <template #header>
            <h3 class="text-xl font-semibold text-secondary-900">📚 Meus Cursos</h3>
          </template>
          <div v-if="loadingEnrollments" class="text-sm text-gray-600">
            Carregando cursos...
          </div>
          <div v-else-if="myEnrollments.length === 0" class="text-gray-600 mb-4">
            <p class="mb-4">Você não está matriculado em nenhum curso ainda.</p>
            <AppLink to="/catalog">
              Explorar cursos →
            </AppLink>
          </div>
          <ul v-else class="space-y-3">
            <li v-for="enrollment in myEnrollments" :key="enrollment.id" class="border border-gray-200 rounded-md p-3 hover:bg-gray-50">
              <AppLink v-if="canPlay(enrollment.status)" :to="`/courses/${enrollment.course_id}/learn`" class="block">
                <div class="font-semibold text-secondary-900">{{ enrollment.course_name }}</div>
                <div class="text-sm text-gray-600">
                  {{ new Date(enrollment.start_date).toLocaleDateString('pt-BR') }} a {{ new Date(enrollment.end_date).toLocaleDateString('pt-BR') }}
                  <span class="ml-2 px-2 py-0.5 rounded text-xs" :class="statusClass(enrollment.status)">{{ enrollment.status }}</span>
                </div>
              </AppLink>
              <div v-else class="block cursor-not-allowed opacity-75">
                <div class="font-semibold text-secondary-900">{{ enrollment.course_name }}</div>
                <div class="text-sm text-gray-600">
                  {{ new Date(enrollment.start_date).toLocaleDateString('pt-BR') }} a {{ new Date(enrollment.end_date).toLocaleDateString('pt-BR') }}
                  <span class="ml-2 px-2 py-0.5 rounded text-xs" :class="statusClass(enrollment.status)">{{ enrollment.status }}</span>
                  <span class="ml-2 text-xs italic">{{ statusMessage(enrollment.status) }}</span>
                </div>
              </div>
            </li>
          </ul>
        </AppCard>

        <!-- Card de Certificados (todos) -->
        <AppCard>
          <template #header>
            <h3 class="text-xl font-semibold text-secondary-900">🏆 Certificados</h3>
          </template>
          <AppLink to="/certificates">
            Ver certificados →
          </AppLink>
        </AppCard>

        <!-- Card de Informações (todos) -->
        <AppCard>
          <template #header>
            <h3 class="text-xl font-semibold text-secondary-900">ℹ️ Meu Perfil</h3>
          </template>
          <div class="space-y-2 text-sm">
            <p><strong>Função:</strong> {{ userRoleDisplay }}</p>
            <p><strong>Nome:</strong> {{ authStore.user?.full_name }}</p>
            <p><strong>E-mail:</strong> {{ authStore.user?.email }}</p>
          </div>
        </AppCard>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useAuthStore } from '../stores/auth'
import api from '../api/client'
import AppNavbar from '../components/AppNavbar.vue'
import AppCard from '../components/AppCard.vue'
import AppLink from '../components/AppLink.vue'

const authStore = useAuthStore()

const roleMap = {
  'admin': 'Administrador',
  'student': 'Aluno'
}

const userRoleDisplay = computed(() => {
  return roleMap[authStore.userRole?.toLowerCase()] || authStore.userRole
})

const isAdmin = computed(() => {
  return authStore.userRole?.toLowerCase() === 'admin'
})

const isStudent = computed(() => {
  return authStore.userRole?.toLowerCase() === 'student'
})

const stats = ref({
  totalStudents: 0,
  activeClasses: 0,
  pendingEnrollments: 0,
  monthlyRevenue: 0,
})

const myEnrollments = ref([])
const loadingEnrollments = ref(false)

const canPlay = (status) => status === 'CONFIRMADA' || status === 'CONCLUIDA'

const statusMessage = (status) => {
  const messages = {
    PENDENTE: 'Aguardando confirmação',
    CANCELADA: 'Matrícula cancelada',
  }
  return messages[status] || ''
}

const statusClass = (status) => {
  const classes = {
    PENDENTE: 'bg-yellow-100 text-yellow-800',
    CONFIRMADA: 'bg-green-100 text-green-800',
    CONCLUIDA: 'bg-blue-100 text-blue-800',
    CANCELADA: 'bg-red-100 text-red-800',
  }
  return classes[status] || 'bg-gray-100 text-gray-800'
}

const loadMyEnrollments = async () => {
  if (!isStudent.value) return
  loadingEnrollments.value = true
  try {
    const response = await api.get('/api/v1/enrollments/me')
    myEnrollments.value = response.data
  } catch (error) {
    console.error('Erro ao carregar matrículas:', error)
  } finally {
    loadingEnrollments.value = false
  }
}

onMounted(() => {
  loadMyEnrollments()
})
</script>
