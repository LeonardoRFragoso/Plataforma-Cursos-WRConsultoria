<template>
  <div class="min-h-screen flex flex-col">
    <!-- Header branco com logo -->
    <header class="bg-white shadow-md border-b border-gray-200">
      <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-3 flex justify-between items-center">
        <router-link to="/" class="flex items-center">
          <img src="../assets/brand/logo-wr-color.png" alt="WR Consultoria e Soluções em QSMS" class="h-12 w-auto" />
        </router-link>
        <AppLink to="/register" variant="primary">
          Cadastre-se
        </AppLink>
      </div>
    </header>

    <div class="flex-1 flex items-center justify-center bg-gray-50 py-12">
      <AppCard class="w-full max-w-md">
        <div class="text-center mb-6">
          <img src="../assets/brand/logo-wr-color.png" alt="WR Consultoria e Soluções em QSMS" class="h-16 w-auto mx-auto mb-4" />
          <h2 class="text-2xl font-bold text-secondary-900">Plataforma de Cursos</h2>
        </div>
        
        <form @submit.prevent="handleLogin" class="space-y-4">
          <AppInput
            v-model="identifier"
            type="text"
            label="CPF ou E-mail"
            placeholder="CPF (11 dígitos) ou seu@email.com"
            required
          />

          <AppInput
            v-model="password"
            type="password"
            label="Senha"
            placeholder="••••••••"
            required
          />

          <AppButton type="submit" :disabled="loading" class="w-full">
            {{ loading ? 'Entrando...' : 'Entrar' }}
          </AppButton>
        </form>

        <div v-if="error" class="mt-4 p-4 bg-red-50 border border-red-200 rounded-md text-red-700 text-sm">
          {{ error }}
        </div>

        <div class="mt-6 text-center space-y-4">
          <p class="text-gray-600">
            Não tem conta?
            <AppLink to="/register" variant="primary">
              Cadastre-se
            </AppLink>
          </p>
          
          <div class="border-t border-gray-200 pt-4">
            <p class="text-sm text-gray-600 mb-3">Dúvidas de acesso?</p>
            <a
              href="https://wa.me/5521974623559?text=Olá,%20preciso%20de%20ajuda%20com%20meu%20acesso%20à%20plataforma%20de%20cursos%20WR"
              target="_blank"
              rel="noopener noreferrer"
              class="inline-flex items-center justify-center space-x-2 bg-green-500 text-white px-4 py-2 rounded-md hover:bg-green-600 transition-colors font-semibold text-sm"
            >
              <svg class="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
                <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.272-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.67-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.076 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421-7.403h-.004a9.87 9.87 0 00-4.255.949c-1.238.503-2.335 1.236-3.356 2.192C3.75 10.645 3.172 12.120 3.172 13.6c0 1.56.378 3.051 1.124 4.381l-.92 3.212a.987.987 0 001.302 1.23l3.22-.84c1.331.738 2.787 1.148 4.168 1.148h.006c5.540 0 10.032-4.61 10.032-10.25 0-2.676-.52-5.365-1.999-7.520-1.476-2.137-3.775-3.528-6.425-3.528z"/>
              </svg>
              <span>Suporte WhatsApp</span>
            </a>
          </div>
        </div>
      </AppCard>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import AppCard from '../components/AppCard.vue'
import AppButton from '../components/AppButton.vue'
import AppInput from '../components/AppInput.vue'
import AppLink from '../components/AppLink.vue'

const router = useRouter()
const authStore = useAuthStore()

const identifier = ref('')
const password = ref('')
const loading = ref(false)
const error = ref('')

const handleLogin = async () => {
  loading.value = true
  error.value = ''
  
  try {
    await authStore.login(identifier.value, password.value)
    router.push('/dashboard')
  } catch (err) {
    error.value = 'CPF/E-mail ou senha inválidos'
  } finally {
    loading.value = false
  }
}
</script>
