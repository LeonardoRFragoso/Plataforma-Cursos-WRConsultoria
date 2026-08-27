<template>
  <div class="fixed bottom-4 right-4 z-[70] sm:bottom-6 sm:right-6" data-testid="nr-tutor-root">
    <transition name="nr-tutor-panel">
      <section
        v-if="open"
        class="mb-3 flex h-[min(70vh,560px)] w-[calc(100vw-2rem)] max-w-[390px] flex-col overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-2xl"
        aria-label="Tutor NR"
      >
        <header class="flex items-center justify-between gap-3 border-b border-slate-100 bg-slate-950 px-4 py-3.5 text-white">
          <div class="flex min-w-0 items-center gap-3">
            <div class="flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl bg-white/10 text-lg">NR</div>
            <div class="min-w-0">
              <p class="truncate text-sm font-black">Tutor NR</p>
              <p class="flex items-center gap-1.5 text-[11px] text-slate-300">
                <span class="h-2 w-2 rounded-full" :class="onlineMode ? 'bg-emerald-400' : 'bg-amber-400'"></span>
                {{ onlineMode ? 'Assistente com base de conhecimento' : 'Assistente virtual de estudo' }}
              </p>
            </div>
          </div>
          <div class="flex items-center gap-1">
            <button type="button" class="rounded-lg p-2 text-slate-300 hover:bg-white/10 hover:text-white" title="Limpar conversa" @click="resetConversation">
              <span aria-hidden="true">↻</span>
            </button>
            <button type="button" class="rounded-lg p-2 text-slate-300 hover:bg-white/10 hover:text-white" title="Fechar" @click="open = false">
              <span aria-hidden="true">×</span>
            </button>
          </div>
        </header>

        <div ref="messagesEl" class="flex-1 space-y-3 overflow-y-auto bg-slate-50/70 px-3 py-4 sm:px-4">
          <div
            v-for="message in messages"
            :key="message.id"
            :class="['flex flex-col', message.role === 'user' ? 'items-end' : 'items-start']"
          >
            <div
              :class="[
                'max-w-[88%] whitespace-pre-line rounded-2xl px-3.5 py-3 text-[13px] leading-5 shadow-sm',
                message.role === 'user'
                  ? 'rounded-br-md bg-[var(--brand-primary)] text-white'
                  : 'rounded-bl-md border border-slate-100 bg-white text-slate-700',
              ]"
            >
              {{ message.text }}
            </div>
            <!-- Sources -->
            <div v-if="message.sources && message.sources.length" class="mt-1.5 flex flex-wrap gap-1 px-1">
              <span
                v-for="source in message.sources"
                :key="source.label"
                class="inline-flex items-center gap-1 rounded-full border border-slate-200 bg-slate-50 px-2 py-0.5 text-[10px] font-medium text-slate-500"
                data-testid="tutor-source-chip"
              >
                <span class="h-1.5 w-1.5 rounded-full bg-emerald-400"></span>
                {{ source.label }}
              </span>
            </div>
            <!-- Confidence indicator -->
            <div v-if="message.confidence && message.role === 'assistant' && message.confidence !== 'HIGH'" class="mt-1 px-1 text-[10px] text-slate-400">
              <span v-if="message.confidence === 'MEDIUM'">Confiança média</span>
              <span v-else>Confiança baixa — reformule para melhor resultado</span>
            </div>
          </div>

          <div v-if="typing" class="flex justify-start">
            <div class="rounded-2xl rounded-bl-md border border-slate-100 bg-white px-4 py-3 text-sm text-slate-400 shadow-sm">
              <span class="inline-flex gap-1" aria-label="Tutor digitando">
                <span class="nr-tutor-dot">•</span><span class="nr-tutor-dot">•</span><span class="nr-tutor-dot">•</span>
              </span>
            </div>
          </div>

          <!-- Error state -->
          <div v-if="error" class="flex flex-col items-start gap-2">
            <div class="max-w-[88%] rounded-2xl rounded-bl-md border border-red-100 bg-red-50 px-3.5 py-3 text-[13px] text-red-700 shadow-sm">
              {{ error }}
            </div>
            <button
              type="button"
              class="rounded-full border border-slate-200 bg-white px-3 py-1.5 text-[11px] font-semibold text-slate-600 hover:border-[var(--brand-primary)] hover:text-[var(--brand-primary)]"
              data-testid="tutor-retry-btn"
              @click="retryLastQuestion"
            >
              Tentar novamente
            </button>
          </div>
        </div>

        <div v-if="currentSuggestions.length" class="flex gap-2 overflow-x-auto border-t border-slate-100 bg-white px-3 py-2.5">
          <button
            v-for="suggestion in currentSuggestions"
            :key="suggestion"
            type="button"
            class="shrink-0 rounded-full border border-slate-200 bg-white px-3 py-1.5 text-[11px] font-semibold text-slate-600 hover:border-[var(--brand-primary)] hover:text-[var(--brand-primary)]"
            @click="sendSuggestion(suggestion)"
          >
            {{ suggestion }}
          </button>
        </div>

        <form class="border-t border-slate-100 bg-white p-3" @submit.prevent="sendMessage">
          <div class="flex items-end gap-2 rounded-2xl border border-slate-200 bg-slate-50 p-2 focus-within:border-[var(--brand-primary)]">
            <textarea
              v-model="draft"
              rows="1"
              maxlength="500"
              class="max-h-28 min-h-[38px] flex-1 resize-none bg-transparent px-2 py-2 text-sm text-slate-800 outline-none placeholder:text-slate-400"
              placeholder="Pergunte sobre qualquer NR..."
              :disabled="typing"
              data-testid="tutor-input"
              @keydown.enter.exact.prevent="sendMessage"
            />
            <button
              type="submit"
              :disabled="!draft.trim() || typing"
              class="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-[var(--brand-primary)] text-white disabled:cursor-not-allowed disabled:opacity-40"
              aria-label="Enviar pergunta"
              data-testid="tutor-send-btn"
            >
              ↑
            </button>
          </div>
          <p class="mt-2 px-1 text-[10px] leading-4 text-slate-400">
            Base educacional da plataforma. Confirme o texto vigente e os procedimentos de SST para decisões de segurança.
          </p>
        </form>
      </section>
    </transition>

    <button
      type="button"
      class="ml-auto flex h-14 items-center gap-2 rounded-2xl bg-slate-950 px-4 text-white shadow-xl transition hover:-translate-y-0.5 hover:shadow-2xl"
      :aria-expanded="open ? 'true' : 'false'"
      aria-label="Abrir Tutor NR"
      data-testid="nr-tutor-toggle"
      @click="open = !open"
    >
      <span class="flex h-8 w-8 items-center justify-center rounded-xl bg-white/10 text-xs font-black">NR</span>
      <span class="hidden text-sm font-bold sm:inline">Tutor NR</span>
      <span class="h-2 w-2 rounded-full bg-emerald-400"></span>
    </button>
  </div>
</template>

<script setup>
import { nextTick, ref, watch } from 'vue'
import { answerNrTutor } from '../utils/nrTutorEngine'
import { askTutor } from '../api/tutor'

const STORAGE_KEY = 'wr_nr_tutor_session_v1'
const open = ref(false)
const draft = ref('')
const typing = ref(false)
const error = ref('')
const messagesEl = ref(null)
const onlineMode = ref(true)
const lastQuestion = ref('')
const currentSuggestions = ref(['Quero estudar NR-6', 'Explique trabalho em altura', 'Quais NRs existem?'])

const welcomeMessage = () => ({
  id: `welcome-${Date.now()}`,
  role: 'assistant',
  text: 'Sou o Tutor NR, assistente virtual de estudo. Posso explicar qualquer NR de 1 a 38, revisar assuntos, comparar normas e ajudar em dúvidas durante a aula — mesmo sobre cursos em que você não está matriculado.',
  sources: [],
  confidence: '',
})

const loadMessages = () => {
  try {
    const parsed = JSON.parse(sessionStorage.getItem(STORAGE_KEY) || '[]')
    if (Array.isArray(parsed) && parsed.length) return parsed.slice(-30)
  } catch {
    // Start a new conversation when session storage is unavailable/corrupted.
  }
  return [welcomeMessage()]
}

const messages = ref(loadMessages())

const persist = () => {
  try {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(messages.value.slice(-30)))
  } catch {
    // Tutor remains functional without persistence.
  }
}

const scrollToBottom = async () => {
  await nextTick()
  if (messagesEl.value) messagesEl.value.scrollTop = messagesEl.value.scrollHeight
}

watch(open, (value) => { if (value) scrollToBottom() })

const append = (role, text, extra = {}) => {
  messages.value.push({ id: `${role}-${Date.now()}-${Math.random()}`, role, text, ...extra })
  messages.value = messages.value.slice(-30)
  persist()
}

const buildConversationContext = () => {
  return messages.value
    .slice(-8)
    .filter((m) => m.text)
    .map((m) => ({ role: m.role, text: m.text }))
}

const sendMessage = async () => {
  const question = draft.value.trim()
  if (!question || typing.value) return
  draft.value = ''
  error.value = ''
  lastQuestion.value = question
  append('user', question)
  currentSuggestions.value = []
  typing.value = true
  await scrollToBottom()

  try {
    const context = buildConversationContext()
    const result = await askTutor(question, context)
    onlineMode.value = true
    append('assistant', result.answer, {
      sources: result.sources || [],
      confidence: result.confidence || '',
      knowledgeLevel: result.knowledge_level || '',
    })
    currentSuggestions.value = result.suggestions || []
  } catch (err) {
    // Fallback to deterministic engine if backend is unavailable
    onlineMode.value = false
    const fallback = answerNrTutor(question)
    append('assistant', fallback.text, { sources: [], confidence: 'LOW' })
    currentSuggestions.value = fallback.suggestions || []
    // Show error only for non-auth issues
    if (err?.response?.status !== 401 && err?.response?.status !== 403) {
      error.value = 'Não foi possível consultar a base de conhecimento. Resposta do modo offline.'
    }
  } finally {
    typing.value = false
    await scrollToBottom()
  }
}

const retryLastQuestion = () => {
  error.value = ''
  if (lastQuestion.value) {
    draft.value = lastQuestion.value
    sendMessage()
  }
}

const sendSuggestion = (suggestion) => {
  draft.value = suggestion
  sendMessage()
}

const resetConversation = () => {
  messages.value = [welcomeMessage()]
  currentSuggestions.value = ['Quero estudar NR-6', 'Explique trabalho em altura', 'Quais NRs existem?']
  error.value = ''
  persist()
  scrollToBottom()
}
</script>

<style scoped>
.nr-tutor-panel-enter-active,
.nr-tutor-panel-leave-active {
  transition: opacity 160ms ease, transform 160ms ease;
}
.nr-tutor-panel-enter-from,
.nr-tutor-panel-leave-to {
  opacity: 0;
  transform: translateY(10px) scale(.98);
}
.nr-tutor-dot {
  animation: nr-tutor-pulse 900ms infinite alternate;
}
.nr-tutor-dot:nth-child(2) { animation-delay: 150ms; }
.nr-tutor-dot:nth-child(3) { animation-delay: 300ms; }
@keyframes nr-tutor-pulse {
  from { opacity: .25; transform: translateY(0); }
  to { opacity: 1; transform: translateY(-2px); }
}
</style>
