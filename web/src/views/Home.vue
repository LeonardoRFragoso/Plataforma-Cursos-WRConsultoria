<template>
  <div class="min-h-screen flex flex-col">
    <!-- Header branco com logo -->
    <header class="bg-white shadow-md border-b border-gray-200">
      <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-3 flex justify-between items-center">
        <router-link to="/" class="flex items-center">
          <img src="../assets/brand/logo-wr-color.png" alt="WR Consultoria e Soluções em QSMS" class="h-12 w-auto" />
        </router-link>
        <nav class="flex items-center space-x-6">
          <router-link to="/login" class="text-gray-700 hover:text-primary-600 font-medium text-sm transition-colors">
            Login
          </router-link>
          <router-link
            to="/register"
            class="bg-primary-600 text-white px-5 py-2 rounded-md hover:bg-primary-700 font-semibold text-sm transition-colors"
          >
            Cadastro
          </router-link>
        </nav>
      </div>
    </header>

    <!-- Hero Section -->
    <section class="relative bg-primary-600 text-white overflow-hidden">
      <div class="absolute inset-0 opacity-15">
        <img
          src="https://images.unsplash.com/photo-1581094794329-c8112a89af12?w=1920&q=80"
          alt="Treinamento de segurança do trabalho"
          class="w-full h-full object-cover"
        />
      </div>
      <div class="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-24 text-center">
        <h1 class="text-4xl sm:text-5xl font-bold mb-6 leading-tight">
          Treinamentos NR com<br />certificação reconhecida
        </h1>
        <p class="text-lg sm:text-xl text-white/90 mb-10 max-w-2xl mx-auto">
          Plataforma de cursos da WR Consultoria e Soluções em QSMS.
          Segurança, qualidade e meio ambiente para sua empresa.
        </p>
        <router-link
          to="/register"
          class="inline-block bg-white text-primary-600 px-8 py-3 rounded-md hover:bg-primary-50 transition-colors text-lg font-semibold shadow-lg"
        >
          Comece Agora
        </router-link>
      </div>
    </section>

    <!-- Features -->
    <section class="flex-1 bg-gray-50 py-20">
      <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div class="text-center mb-16">
          <h2 class="text-3xl font-bold text-secondary-900 mb-4">Por que escolher a WR?</h2>
          <p class="text-gray-600 max-w-2xl mx-auto">
            Mais de uma década de experiência em consultoria QSMS para empresas de todos os portes.
          </p>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-3 gap-8">
          <!-- Cursos Variados -->
          <div class="bg-white p-8 rounded-lg shadow-md hover:shadow-lg transition-shadow border border-gray-200">
            <div class="w-12 h-12 bg-primary-50 rounded-lg flex items-center justify-center mb-5">
              <svg class="w-7 h-7 text-primary-600" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
                <path stroke-linecap="round" stroke-linejoin="round" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
              </svg>
            </div>
            <h3 class="text-xl font-semibold text-secondary-900 mb-2">Cursos Variados</h3>
            <p class="text-gray-600">Acesso a diversos cursos NR com conteúdo atualizado, instrutores qualificados e material didático completo.</p>
          </div>

          <!-- Certificação -->
          <div class="bg-white p-8 rounded-lg shadow-md hover:shadow-lg transition-shadow border border-gray-200">
            <div class="w-12 h-12 bg-primary-50 rounded-lg flex items-center justify-center mb-5">
              <svg class="w-7 h-7 text-primary-600" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
                <path stroke-linecap="round" stroke-linejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
            <h3 class="text-xl font-semibold text-secondary-900 mb-2">Certificação</h3>
            <p class="text-gray-600">Receba certificados válidos com código de verificação após conclusão dos cursos e avaliação final.</p>
          </div>

          <!-- Plataforma Moderna -->
          <div class="bg-white p-8 rounded-lg shadow-md hover:shadow-lg transition-shadow border border-gray-200">
            <div class="w-12 h-12 bg-primary-50 rounded-lg flex items-center justify-center mb-5">
              <svg class="w-7 h-7 text-primary-600" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
                <path stroke-linecap="round" stroke-linejoin="round" d="M9 17.25v1.007a3 3 0 01-.879 2.122L7.5 21h9l-.621-.621A3 3 0 0115 18.257V17.25m6-12V15a2.25 2.25 0 01-2.25 2.25H5.25A2.25 2.25 0 013 15V5.25m18 0A2.25 2.25 0 0018.75 3H5.25A2.25 2.25 0 003 5.25m18 0V12a2.25 2.25 0 01-2.25 2.25H5.25A2.25 2.25 0 013 12V5.25" />
              </svg>
            </div>
            <h3 class="text-xl font-semibold text-secondary-900 mb-2">Plataforma Moderna</h3>
            <p class="text-gray-600">Acesso fácil e intuitivo de qualquer dispositivo. Cursos presenciais, EAD ou semipresenciais.</p>
          </div>
        </div>
      </div>
    </section>

    <!-- Footer -->
    <footer class="bg-primary-700 text-white/80 py-8">
      <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
        <img src="../assets/brand/logo-wr-white.png" alt="WR Consultoria e Soluções em QSMS" class="h-10 w-auto mx-auto mb-4" />
        <p class="text-sm">WR Consultoria e Soluções em QSMS — Treinamentos NR com certificação</p>
        <p class="text-xs text-white/50 mt-2">&copy; 2026 WR Consultoria. Todos os direitos reservados.</p>
      </div>
    </footer>
  </div>
</template>

<script setup>
</script>
