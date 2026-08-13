<template>
  <div class="min-h-screen bg-gray-50">
    <AppNavbar />

    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <h1 class="text-3xl font-bold text-secondary-900 mb-8">Dashboard</h1>

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

      <div class="grid grid-cols-1 md:grid-cols-3 gap-8">
        <AppCard v-if="isAdmin">
          <template #header>
            <h3 class="text-xl font-semibold text-secondary-900">Gerenciamento</h3>
          </template>
          <div class="space-y-2">
            <AppLink to="/courses">
              → Cursos
            </AppLink>
            <AppLink to="/classes">
              → Turmas
            </AppLink>
            <AppLink to="/students">
              → Alunos
            </AppLink>
            <AppLink to="/enrollments">
              → Matrículas
            </AppLink>
            <AppLink to="/payments">
              → Pagamentos
            </AppLink>
          </div>
        </AppCard>

        <AppCard>
          <template #header>
            <h3 class="text-xl font-semibold text-secondary-900">Meus Cursos</h3>
          </template>
          <p class="text-gray-600">Você não está matriculado em nenhum curso ainda.</p>
        </AppCard>

        <AppCard>
          <template #header>
            <h3 class="text-xl font-semibold text-secondary-900">Certificados</h3>
          </template>
          <AppLink to="/certificates">
            Ver certificados →
          </AppLink>
        </AppCard>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import AppNavbar from '../components/AppNavbar.vue'
import AppCard from '../components/AppCard.vue'
import AppLink from '../components/AppLink.vue'

const router = useRouter()
const authStore = useAuthStore()

const isAdmin = computed(() => authStore.userRole === 'admin')

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
</script>
