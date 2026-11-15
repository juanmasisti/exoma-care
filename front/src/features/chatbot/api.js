import { api } from '../../services/api.js'

export async function chatbotStatus(signal) {
  const { data } = await api.get('/chatbot/status', { signal, timeout: 25000 })
  return data
}

export function waitForRetry(seconds, signal) {
  return new Promise((resolve, reject) => {
    if (signal.aborted) { reject(new Error('Cancelled')); return }
    const abort = () => { clearTimeout(timer); reject(new Error('Cancelled')) }
    const timer = setTimeout(() => { signal.removeEventListener('abort', abort); resolve() }, seconds * 1000)
    signal.addEventListener('abort', abort, { once: true })
  })
}

export async function askChatbot(question, conversationToken, signal, onRetry = () => {}, wait = waitForRetry) {
  for (let attempt = 0; attempt < 2; attempt++) {
    try {
      const { data } = await api.post('/chatbot/messages', { question, conversation_token: conversationToken }, { signal, timeout: 25000 })
      if (typeof data.answer !== 'string' || !data.answer.trim() || typeof data.conversation_token !== 'string') throw new Error('Invalid chatbot response')
      return data
    } catch (error) {
      if (signal.aborted || error.response?.status !== 429 || attempt === 1) throw error
      const value = Number(error.response.headers?.['retry-after'])
      const seconds = Number.isFinite(value) && value > 0 ? Math.min(Math.ceil(value), 86400) : 5
      onRetry(seconds)
      await wait(seconds, signal)
      onRetry(null)
    }
  }
}
