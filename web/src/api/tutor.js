import api from './client'

/**
 * Tutor NR API client.
 * Sends questions to the backend retrieval-augmented engine.
 */

/**
 * Ask the NR Tutor a question.
 * @param {string} question - The student's question
 * @param {Array<{role: string, text: string}>} conversationContext - Recent messages
 * @returns {Promise<{answer: string, sources: Array, suggestions: Array, confidence: string, scope: Array, knowledge_level: string}>}
 */
export async function askTutor(question, conversationContext = []) {
  const { data } = await api.post('/api/v1/tutor/ask', {
    question,
    conversation_context: conversationContext,
  })
  return data
}

/**
 * Get knowledge coverage status (15 sources).
 * @returns {Promise<{total_expected: number, total_indexed: number, total_chunks: number, sources: Array, all_covered: boolean}>}
 */
export async function getTutorCoverage() {
  const { data } = await api.get('/api/v1/tutor/coverage')
  return data
}
