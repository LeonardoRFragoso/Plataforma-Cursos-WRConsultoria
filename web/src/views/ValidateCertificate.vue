<template>
  <div class="min-h-screen bg-gray-50 flex flex-col">
    <header class="bg-primary-600 text-white py-6">
      <div class="max-w-3xl mx-auto px-4 text-center">
        <h1 class="text-2xl font-bold">Validar certificado</h1>
        <p class="text-white/80 text-sm mt-1">Confirme a autenticidade de um certificado emitido na plataforma.</p>
      </div>
    </header>

    <main class="flex-1 flex items-center justify-center p-6">
      <div class="w-full max-w-md bg-white rounded-lg shadow-lg p-8">
        <form class="space-y-4" @submit.prevent="handleSubmit">
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">Código de validação</label>
            <input
              v-model="code"
              type="text"
              required
              placeholder="Cole o código aqui"
              class="w-full p-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-600"
            />
          </div>
          <button
            type="submit"
            class="w-full py-3 bg-primary-600 text-white font-semibold rounded-lg hover:bg-primary-700 transition"
          >
            Verificar
          </button>
        </form>

        <div v-if="result" class="mt-6 p-4 rounded-lg" :class="result.valid ? 'bg-green-50 text-green-800' : 'bg-red-50 text-red-800'">
          <div v-if="result.valid" class="space-y-2">
            <p class="font-bold">Certificado válido</p>
            <p class="text-sm"><span class="font-medium">Número:</span> {{ result.certificate_number }}</p>
            <p class="text-sm"><span class="font-medium">Aluno:</span> {{ result.student_name }}</p>
            <p class="text-sm"><span class="font-medium">Curso:</span> {{ result.course_name }}</p>
            <p class="text-sm"><span class="font-medium">Emitido em:</span> {{ formatDate(result.issued_at) }}</p>
          </div>
          <div v-else>
            <p class="font-bold">Código não encontrado</p>
            <p class="text-sm">O certificado não foi localizado em nossa base de dados.</p>
          </div>
        </div>
      </div>
    </main>

    <footer class="bg-gray-100 py-4 text-center text-sm text-gray-500">
      &copy; 2026 WR Consultoria. Todos os direitos reservados.
    </footer>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { validateCertificate } from '../api/certificates'

const code = ref('')
const result = ref(null)

function formatDate(value) {
  if (!value) return '-'
  return new Date(value).toLocaleDateString('pt-BR')
}

async function handleSubmit() {
  try {
    const { data } = await validateCertificate(code.value)
    result.value = data
  } catch {
    result.value = { valid: false }
  }
}
</script>
