import { useEffect, useRef, useState } from 'react'
import { MessageCircle, Send } from 'lucide-react'
import ClinicalLayout from '../../components/layout/ClinicalLayout.jsx'
import { errorMessage } from '../../services/api.js'
import { askChatbot, chatbotStatus } from './api.js'
import './chatbot.css'

export default function PatientChat({ session }) {
  const [status, setStatus] = useState('loading')
  const [question, setQuestion] = useState('')
  const [messages, setMessages] = useState([])
  const [pendingQuestion, setPendingQuestion] = useState(null)
  const [sending, setSending] = useState(false)
  const [error, setError] = useState('')
  const [availabilityMessage, setAvailabilityMessage] = useState('')
  const [conversationToken, setConversationToken] = useState(null)
  const [retrySeconds, setRetrySeconds] = useState(null)
  const availabilityRequest = useRef(null)
  const messageRequest = useRef(null)
  const messageLog = useRef(null)

  function checkAvailability() {
    availabilityRequest.current?.abort()
    const controller = new AbortController()
    availabilityRequest.current = controller
    chatbotStatus(controller.signal).then(data => {
      if (!controller.signal.aborted) {
        setStatus(data.available === true ? 'available' : 'unavailable')
        setAvailabilityMessage(typeof data.message === 'string' ? data.message : '')
      }
    }).catch(() => {
      if (!controller.signal.aborted) setStatus('error')
    }).finally(() => {
      if (availabilityRequest.current === controller) availabilityRequest.current = null
    })
  }

  useEffect(() => {
    checkAvailability()
    return () => {
      availabilityRequest.current?.abort()
      messageRequest.current?.abort()
    }
  }, [])

  useEffect(() => {
    const log = messageLog.current
    if (log) log.scrollTop = log.scrollHeight
  }, [messages, pendingQuestion, sending, retrySeconds])

  async function send(event) {
    event.preventDefault()
    const text = question.trim()
    if (messageRequest.current || status !== 'available' || !text || text.length > 1000) return
    const controller = new AbortController()
    messageRequest.current = controller
    setPendingQuestion(text)
    setSending(true); setError('')
    try {
      const result = await askChatbot(text, conversationToken, controller.signal, seconds => {
        if (!controller.signal.aborted) setRetrySeconds(seconds)
      })
      if (controller.signal.aborted) return
      setMessages(previous => [...previous, { role: 'Vos', text }, { role: 'Asistente automático', text: result.answer }])
      setPendingQuestion(null)
      setConversationToken(result.conversation_token)
      setQuestion('')
    } catch (failure) {
      if (!controller.signal.aborted) setError(errorMessage(failure))
    } finally {
      if (messageRequest.current === controller) messageRequest.current = null
      if (!controller.signal.aborted) { setSending(false); setRetrySeconds(null) }
    }
  }

  return <ClinicalLayout session={session} pageLabel="Consultas">
    <section className="patient-chat" aria-labelledby="chat-title">
      <header className="chat-heading"><span>ORIENTACIÓN PARA PACIENTES</span><h1 id="chat-title"><MessageCircle aria-hidden="true" />Consultas sobre estudios genéticos</h1>
        <p>Información general sobre estudios genéticos y sobre Fabry, Gaucher, Pompe, ASMD y mucopolisacaridosis tipo I.</p>
      </header>
      <div className="chat-panel">
        <p className="chat-help">Este asistente automático brinda información general y no reemplaza a tu médico. No incluyas nombres, DNI, email, teléfono ni resultados personales.</p>
        <div className="chat-availability" role="status">
          {status === 'loading' ? 'Comprobando disponibilidad…' : status === 'unavailable' ? (availabilityMessage || 'El servicio de consultas aún no está disponible.') : status === 'error' ? 'No pudimos comprobar la disponibilidad. Intentá nuevamente.' : 'Podés enviar tu pregunta.'}
        </div>
        {['unavailable', 'error'].includes(status) && <button className="chat-secondary" type="button" onClick={() => { setStatus('loading'); checkAvailability() }}>Verificar disponibilidad</button>}
        {(conversationToken || messages.length > 0 || error) && <button className="chat-secondary" type="button" disabled={sending} onClick={() => { setConversationToken(null); setMessages([]); setPendingQuestion(null); setError('') }}>Nueva conversación</button>}
        {messages.length > 0 && <button className="chat-secondary" type="button" onClick={() => {
          const log = messageLog.current
          if (log) { log.scrollTop = log.scrollHeight; log.lastElementChild?.focus() }
        }}>Ver última respuesta</button>}
        <div ref={messageLog} className="chat-messages" role="log" aria-label="Preguntas y respuestas" aria-live="polite" aria-relevant="additions">
          {!messages.length && !pendingQuestion && <p className="chat-empty">Tus preguntas y respuestas aparecerán aquí.</p>}
          {messages.map((message, index) => <article key={index} tabIndex={-1} className={`chat-message ${message.role === 'Vos' ? 'chat-question' : ''}`}><strong>{message.role}</strong><p>{message.text}</p></article>)}
          {pendingQuestion && <article className="chat-message chat-question"><strong>Vos</strong><p>{pendingQuestion}</p>{!sending && error && <small>No se recibió una respuesta. Podés editar y reenviar tu pregunta.</small>}</article>}
          {sending && <article className="chat-message chat-generating"><strong>Asistente automático</strong><p role="status">{retrySeconds ? `Se alcanzó el límite de consultas. Reintentaremos una sola vez después de ${retrySeconds} segundos.` : <><span className="chat-typing" aria-hidden="true"><i /><i /><i /></span>Preparando respuesta…</>}</p></article>}
        </div>
        <form onSubmit={send}>
          <label htmlFor="chat-question">Tu pregunta</label>
          <textarea id="chat-question" rows={3} maxLength={1000} value={question} disabled={sending || status !== 'available'} onChange={event => setQuestion(event.target.value)} aria-describedby="chat-question-help" placeholder="Escribí tu consulta sobre estudios genéticos o estas patologías" />
          <p id="chat-question-help" className="chat-help">Hasta 1.000 caracteres. Podés hacer preguntas relacionadas. El servicio recuerda los últimos 6 intercambios durante 30 minutos de inactividad. Al salir de esta pantalla, se pierde el historial visible.</p>
          {error && <p className="chat-error" role="alert">{error} Tu pregunta sigue escrita para que puedas volver a enviarla.</p>}
          <button className="chat-send" type="submit" disabled={sending || status !== 'available' || !question.trim()}><Send size={17} aria-hidden="true" />{sending ? 'Enviando…' : 'Enviar pregunta'}</button>
        </form>
      </div>
    </section>
  </ClinicalLayout>
}
