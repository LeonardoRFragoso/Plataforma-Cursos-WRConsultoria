<template>
  <div class="min-h-screen bg-gray-50">
    <nav class="bg-white shadow-sm border-b border-gray-200">
      <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4 flex justify-between items-center">
        <div class="flex items-center space-x-2">
          <div class="text-2xl font-bold text-primary-600">WR</div>
          <div class="text-sm text-gray-600">Consultoria</div>
        </div>
        <div class="space-x-4 flex items-center">
          <span class="text-gray-600">{{ authStore.user?.full_name }}</span>
          <button
            @click="handleLogout"
            class="text-red-600 hover:text-red-700 font-semibold transition-colors"
          >
            Sair
          </button>
        </div>
      </div>
    </nav>

    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <h1 class="text-3xl font-bold text-secondary-900 mb-8">Dashboard</h1>

      <div v-if="isAdmin" class="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
        <div class="bg-white p-6 rounded-lg shadow-md border border-gray-200">
          <div class="text-gray-600 text-sm">Total de Alunos</div>
          <div class="text-3xl font-bold text-primary-600">{{ stats.totalStudents }}</div>
        </div>
        <div class="bg-white p-6 rounded-lg shadow-md border border-gray-200">
          <div class="text-gray-600 text-sm">Turmas Ativas</div>
          <div class="text-3xl font-bold text-primary-600">{{ stats.activeClasses }}</div>
        </div>
        <div class="bg-white p-6 rounded-lg shadow-md border border-gray-200">
          <div class="text-gray-600 text-sm">Matrículas Pendentes</div>
          <div class="text-3xl font-bold text-primary-600">{{ stats.pendingEnrollments }}</div>
        </div>
        <div class="bg-white p-6 rounded-lg shadow-md border border-gray-200">
          <div class="text-gray-600 text-sm">Receita do Mês</div>
          <div class="text-3xl font-bold text-primary-600">R$ {{ stats.monthlyRevenue }}</div>
        </div>
      </div>

      <div class="grid grid-cols-1 md:grid-cols-3 gap-8">
        <div v-if="isAdmin" class="bg-white p-6 rounded-lg shadow-md border border-gray-200">
          <h3 class="text-xl font-semibold text-secondary-900 mb-4">Gerenciamento</h3>
          <div class="space-y-2">
            <router-link to="/courses" class="block text-primary-600 hover:text-primary-700 transition-colors">
              → Cursos
            </router-link>
            <router-link to="/classes" class="block text-primary-600 hover:text-primary-700 transition-colors">
              → Turmas
            </router-link>
            <router-link to="/students" class="block text-primary-600 hover:text-primary-700 transition-colors">
              → Alunos
            </router-link>
            <router-link to="/enrollments" class="block text-primary-600 hover:text-primary-700 transition-colors">
              → Matrículas
            </router-link>
            <router-link to="/payments" class="block text-primary-600 hover:text-primary-700 transition-colors">
              → Pagamentos
            </router-link>
          </div>
        </div>

        <div class="bg-white p-6 rounded-lg shadow-md border border-gray-200">
          <h3 class="text-xl font-semibold text-secondary-900 mb-4">Meus Cursos</h3>
          <p class="text-gray-600">Você não está matriculado em nenhum curso ainda.</p>
        </div>

        <div class="bg-white p-6 rounded-lg shadow-md border border-gray-200">
          <h3 class="text-xl font-semibold text-secondary-900 mb-4">Certificados</h3>
          <router-link to="/certificates" class="text-primary-600 hover:text-primary-700 transition-colors">
            Ver certificados →
          </router-link>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'

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
