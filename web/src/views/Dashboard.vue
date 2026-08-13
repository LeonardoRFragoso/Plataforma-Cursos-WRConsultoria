<template>
  <div class="min-h-screen bg-gray-50">
    <AppNavbar />

    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <h1 class="text-3xl font-bold text-secondary-900 mb-8">Dashboard</h1>

      <!-- Debug Info -->
      <div class="mb-4 p-4 bg-blue-50 border border-blue-200 rounded text-sm text-blue-700">
        <strong>Debug:</strong> userRole={{ authStore.userRole }}, isAdmin={{ isAdmin }}, isInstructor={{ isInstructor }}, isStudent={{ isStudent }}
      </div>

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

        <!-- Card de Cursos do Instrutor (INSTRUCTOR) -->
        <AppCard v-if="isInstructor">
          <template #header>
            <h3 class="text-xl font-semibold text-secondary-900">📚 Meus Cursos</h3>
          </template>
          <p class="text-gray-600 mb-4">Você não tem cursos atribuídos ainda.</p>
          <AppLink to="/courses">
            Ver todos os cursos →
          </AppLink>
        </AppCard>

        <!-- Card de Cursos do Aluno (STUDENT) -->
        <AppCard v-if="isStudent">
          <template #header>
            <h3 class="text-xl font-semibold text-secondary-900">📚 Meus Cursos</h3>
          </template>
          <p class="text-gray-600 mb-4">Você não está matriculado em nenhum curso ainda.</p>
          <AppLink to="/courses">
            Explorar cursos →
          </AppLink>
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
import { ref, computed, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import AppNavbar from '../components/AppNavbar.vue'
import AppCard from '../components/AppCard.vue'
import AppLink from '../components/AppLink.vue'

const router = useRouter()
const authStore = useAuthStore()

const roleMap = {
  'ADMIN': 'Administrador',
  'INSTRUCTOR': 'Instrutor',
  'STUDENT': 'Aluno'
}

const userRoleDisplay = computed(() => {
  return roleMap[authStore.userRole] || authStore.userRole
})

const isAdmin = computed(() => {
  const result = authStore.userRole === 'ADMIN'
  console.log('isAdmin computed:', { userRole: authStore.userRole, result })
  return result
})

const isInstructor = computed(() => {
  return authStore.userRole === 'INSTRUCTOR'
})

const isStudent = computed(() => {
  return authStore.userRole === 'STUDENT'
})

const stats = ref({
  totalStudents: 0,
  activeClasses: 0,
  pendingEnrollments: 0,
  monthlyRevenue: 0,
})

const handleLogout = () => {
  authStore.logout()
  router.push('/login')
}

// Debug
watch(() => authStore.userRole, (newRole) => {
  console.log('Dashboard: userRole changed to', newRole)
})
</script>
