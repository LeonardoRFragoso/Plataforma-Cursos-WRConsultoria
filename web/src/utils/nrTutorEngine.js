import { NR_BY_NUMBER, NR_KNOWLEDGE, OFFICIAL_NR_NOTE } from '../data/nrTutorKnowledge'

const STOP_WORDS = new Set([
  'a', 'ao', 'aos', 'as', 'com', 'como', 'da', 'das', 'de', 'do', 'dos', 'e', 'em', 'eu', 'me', 'na', 'nas',
  'no', 'nos', 'o', 'os', 'para', 'por', 'pra', 'que', 'qual', 'quais', 'se', 'sobre', 'um', 'uma', 'uns', 'umas',
])

function normalize(value = '') {
  return String(value)
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .replace(/[^a-z0-9\s-]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
}

function tokens(value) {
  return normalize(value)
    .split(' ')
    .filter((token) => token.length > 1 && !STOP_WORDS.has(token))
}

function extractNrNumbers(text) {
  const found = []
  for (const match of normalize(text).matchAll(/\bnr\s*-?\s*(\d{1,2})\b/g)) {
    const number = Number(match[1])
    if (NR_BY_NUMBER[number] && !found.includes(number)) found.push(number)
  }
  return found
}

function scoreKnowledge(query, item) {
  const normalized = normalize(query)
  const queryTokens = new Set(tokens(query))
  let score = 0

  if (normalized.includes(`nr ${item.number}`) || normalized.includes(`nr-${item.number}`)) score += 20
  if (normalized.includes(normalize(item.title))) score += 15

  for (const keyword of item.keywords || []) {
    const normalizedKeyword = normalize(keyword)
    if (normalized.includes(normalizedKeyword)) score += 8
    for (const token of tokens(keyword)) {
      if (queryTokens.has(token)) score += 2
    }
  }

  for (const point of item.keyPoints || []) {
    for (const token of tokens(point)) {
      if (queryTokens.has(token)) score += 1
    }
  }

  return score
}

function findBestKnowledge(query) {
  return NR_KNOWLEDGE
    .map((item) => ({ item, score: scoreKnowledge(query, item) }))
    .sort((a, b) => b.score - a.score)[0]
}

function findFaq(query, item) {
  const normalized = normalize(query)
  let best = null
  let bestScore = 0
  for (const faq of item.faq || []) {
    let score = 0
    for (const term of faq.terms || []) {
      const normalizedTerm = normalize(term)
      if (normalized.includes(normalizedTerm)) score += 5
      for (const token of tokens(term)) {
        if (normalized.includes(token)) score += 1
      }
    }
    if (score > bestScore) {
      best = faq
      bestScore = score
    }
  }
  return bestScore >= 2 ? best : null
}

function formatOverview(item, detailed = false) {
  if (item.status === 'revogada') {
    return `NR-${item.number} — ${item.title}\n\n${item.summary}\n\nStatus: REVOGADA. Para uma situação atual, use os requisitos vigentes aplicáveis e não trate o texto antigo como obrigação atual.`
  }

  const points = (item.keyPoints || []).map((point) => `• ${point}`).join('\n')
  const intro = `NR-${item.number} — ${item.title}\n\n${item.summary}`
  if (!detailed || !points) return intro
  return `${intro}\n\nPontos principais para estudar:\n${points}`
}

function compareNrs(first, second) {
  const a = NR_BY_NUMBER[first]
  const b = NR_BY_NUMBER[second]
  if (!a || !b) return null
  return `Comparando as duas normas:\n\nNR-${a.number} — ${a.title}\n${a.summary}\n\nNR-${b.number} — ${b.title}\n${b.summary}\n\nEm resumo: a NR-${a.number} concentra-se em ${a.keyPoints?.[0]?.toLowerCase() || 'seu campo específico'}, enquanto a NR-${b.number} concentra-se em ${b.keyPoints?.[0]?.toLowerCase() || 'seu campo específico'}. Elas podem se aplicar ao mesmo trabalho ao mesmo tempo, dependendo dos riscos e da atividade.`
}

function listNrs() {
  const lines = NR_KNOWLEDGE.map((item) => `NR-${item.number}: ${item.title}${item.status === 'revogada' ? ' (revogada)' : ''}`)
  return `A base do Tutor NR cobre NR-1 a NR-38, inclusive as normas revogadas NR-2 e NR-27 para fins de contexto.\n\n${lines.join('\n')}`
}

function suggestedQuestions(item) {
  if (!item) return ['O que é NR-35?', 'Qual NR fala sobre EPI?', 'Quais NRs existem?']
  const suggestions = [
    `Resuma a NR-${item.number}`,
    `Quais os pontos principais da NR-${item.number}?`,
  ]
  if (item.faq?.length) {
    const firstTerm = item.faq[0].terms?.[0]
    if (firstTerm) suggestions.push(`Explique ${firstTerm} na NR-${item.number}`)
  }
  return suggestions.slice(0, 3)
}

export function answerNrTutor(question) {
  const input = String(question || '').trim()
  const normalized = normalize(input)

  if (!input) {
    return { text: 'Escreva sua dúvida sobre uma NR, um risco ou um tema de Segurança e Saúde no Trabalho.', suggestions: suggestedQuestions() }
  }

  if (/^(oi|ola|bom dia|boa tarde|boa noite|e ai|hey)\b/.test(normalized)) {
    return {
      text: 'Olá. Sou o Tutor NR, assistente virtual de estudo da plataforma. Posso explicar temas, revisar pontos importantes, comparar NRs e ajudar você a estudar qualquer NR de 1 a 38. Não é necessário estar matriculado no curso da NR para perguntar.',
      suggestions: ['Quero estudar NR-6', 'Explique trabalho em altura', 'Quais NRs existem?'],
    }
  }

  if (normalized.includes('quais nrs') || normalized.includes('lista de nrs') || normalized.includes('todas as nrs')) {
    return { text: listNrs(), suggestions: ['Quais NRs estão revogadas?', 'Quero estudar NR-10', 'Explique NR-1'] }
  }

  if (normalized.includes('revogad')) {
    return {
      text: 'Na sequência NR-1 a NR-38, a NR-2 (Inspeção Prévia) e a NR-27 (Registro Profissional do Técnico de Segurança do Trabalho) estão revogadas. O Tutor mantém essas referências apenas para contexto histórico e sempre indica o status.',
      suggestions: ['Explique NR-1', 'Explique NR-28', 'Quais NRs existem?'],
    }
  }

  const explicitNrs = extractNrNumbers(input)
  if (explicitNrs.length >= 2 && /(diferen|compar|versus| vs | x )/.test(` ${normalized} `)) {
    return {
      text: compareNrs(explicitNrs[0], explicitNrs[1]),
      suggestions: [`Resuma a NR-${explicitNrs[0]}`, `Resuma a NR-${explicitNrs[1]}`, 'Quais NRs existem?'],
    }
  }

  let item = explicitNrs.length ? NR_BY_NUMBER[explicitNrs[0]] : null
  if (!item) {
    const best = findBestKnowledge(input)
    if (best?.score >= 3) item = best.item
  }

  if (!item) {
    return {
      text: `Não encontrei uma NR específica com confiança suficiente para responder essa pergunta sem inventar informação. Tente citar o número da NR ou um tema como “EPI”, “eletricidade”, “máquinas”, “espaço confinado” ou “trabalho em altura”.\n\n${OFFICIAL_NR_NOTE}`,
      suggestions: ['Qual NR fala sobre EPI?', 'Qual NR fala sobre eletricidade?', 'Quais NRs existem?'],
    }
  }

  const faq = findFaq(input, item)
  if (faq) {
    return {
      text: `NR-${item.number} — ${item.title}\n\n${faq.answer}\n\n${OFFICIAL_NR_NOTE}`,
      suggestions: suggestedQuestions(item),
    }
  }

  const wantsStudy = /(estudar|estudo|resumo|resuma|revis|pontos|principais|conteudo|conteúdo)/.test(normalized)
  const asksWhat = /(o que e|o que é|qual objetivo|para que serve|explique|fala sobre)/.test(normalized)

  if (wantsStudy || asksWhat || explicitNrs.length) {
    return {
      text: `${formatOverview(item, wantsStudy || normalized.includes('pontos'))}\n\n${OFFICIAL_NR_NOTE}`,
      suggestions: suggestedQuestions(item),
    }
  }

  return {
    text: `${formatOverview(item, true)}\n\nSua pergunta parece estar relacionada a esta norma. Se quiser, reformule citando o ponto exato da dúvida para eu procurar uma resposta mais específica dentro da base.\n\n${OFFICIAL_NR_NOTE}`,
    suggestions: suggestedQuestions(item),
  }
}

export { normalize, extractNrNumbers, findBestKnowledge }
