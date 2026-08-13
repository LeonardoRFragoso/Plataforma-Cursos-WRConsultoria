<template>
  <div class="min-h-screen bg-gradient-to-br from-primary-50 to-gray-50">
    <nav class="bg-white shadow-sm border-b border-gray-200">
      <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4 flex justify-between items-center">
        <div class="flex items-center space-x-3">
          <img src="../assets/logo-wr.png" alt="WR Consultoria" class="h-10 w-auto" />
        </div>
        <div class="space-x-4">
          <router-link to="/login" class="text-primary-600 hover:text-primary-700 font-medium">Login</router-link>
          <router-link to="/register" class="bg-primary-600 text-white px-4 py-2 rounded-md hover:bg-primary-700 transition-colors">
            Cadastro
          </router-link>
        </div>
      </div>
    </nav>

    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-16">
      <div class="text-center mb-16">
        <h1 class="text-5xl font-bold text-secondary-900 mb-4">Plataforma de Cursos NR</h1>
        <p class="text-xl text-gray-600 mb-8">
          Treinamentos normativos de qualidade para sua segurança no trabalho
        </p>
        <router-link to="/register" class="inline-block bg-primary-600 text-white px-8 py-3 rounded-md hover:bg-primary-700 transition-colors text-lg font-semibold">
          Comece Agora
        </router-link>
      </div>

      <div class="grid grid-cols-1 md:grid-cols-3 gap-8">
        <div class="bg-white p-8 rounded-lg shadow-md hover:shadow-lg transition-shadow border border-gray-200">
          <div class="text-4xl mb-4">📚</div>
          <h3 class="text-xl font-semibold text-secondary-900 mb-2">Cursos Variados</h3>
          <p class="text-gray-600">Acesso a diversos cursos NR com conteúdo atualizado e certificação.</p>
        </div>
        <div class="bg-white p-8 rounded-lg shadow-md hover:shadow-lg transition-shadow border border-gray-200">
          <div class="text-4xl mb-4">🎓</div>
          <h3 class="text-xl font-semibold text-secondary-900 mb-2">Certificação</h3>
          <p class="text-gray-600">Receba certificados válidos após conclusão dos cursos.</p>
        </div>
        <div class="bg-white p-8 rounded-lg shadow-md hover:shadow-lg transition-shadow border border-gray-200">
          <div class="text-4xl mb-4">💻</div>
          <h3 class="text-xl font-semibold text-secondary-900 mb-2">Plataforma Moderna</h3>
          <p class="text-gray-600">Acesso fácil e intuitivo de qualquer dispositivo.</p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
</script>
