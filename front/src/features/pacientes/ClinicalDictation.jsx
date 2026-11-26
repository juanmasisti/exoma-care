import { useEffect, useId, useRef, useState } from 'react'
import { Mic, Square, X, Plus } from 'lucide-react'
import './dictation.css'

const MAX_SUMMARY = 20000
const errors = {
  'not-allowed': 'No se autorizó el micrófono. Revisá el permiso del sitio o escribí manualmente.',
  'service-not-allowed': 'El navegador no permite este servicio de voz. Podés escribir manualmente.',
  'audio-capture': 'No se pudo acceder al micrófono. Comprobá que esté conectado y disponible.',
  'no-speech': 'No se reconoció voz. Podés volver a intentar o escribir manualmente.',
  network: 'No se pudo conectar con el servicio de dictado. Revisá tu conexión; si usás Brave, probá abrir esta página en Chrome. Podés seguir escribiendo manualmente.',
  'language-not-supported': 'El servicio no admite el idioma español configurado. Podés escribir manualmente.',
  aborted: 'El dictado se interrumpió. Revisá el texto reconocido antes de continuar.',
}

export default function ClinicalDictation({ summary, onApply, onPendingChange, disabled = false }) {
  const [phase, setPhase] = useState('idle')
  const [draft, setDraft] = useState('')
  const [reviewVisible, setReviewVisible] = useState(false)
  const [interim, setInterim] = useState('')
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const session = useRef(null)
  const id = useId()
  const Recognition = typeof window === 'undefined' ? null : window.SpeechRecognition || window.webkitSpeechRecognition
  const secure = typeof window !== 'undefined' && window.isSecureContext !== false
  const active = phase !== 'idle'
  const pending = active || Boolean(draft.trim())
  const combined = summary + (summary && draft.trim() ? '\n\n' : '') + draft.trim()
  const tooLong = combined.length > MAX_SUMMARY

  useEffect(() => { onPendingChange(pending) }, [pending, onPendingChange])
  useEffect(() => () => {
    const current = session.current
    session.current = null
    if (current) {
      clearTimeout(current.timer)
      try { current.recognition.abort() } catch { /* Already ended. */ }
    }
  }, [])

  // Invalidate callbacks before abort: some providers dispatch error/end synchronously.
  function release(current) {
    if (session.current !== current) return
    session.current = null
    clearTimeout(current.timer)
    try { current.recognition.abort() } catch { /* Already ended. */ }
    setPhase('idle'); setInterim('')
  }

  function start() {
    if (!Recognition || !secure || disabled || session.current || draft.trim()) return
    setError(''); setNotice(''); setDraft(''); setReviewVisible(false); setInterim(''); setPhase('starting')
    let current
    try {
      const recognition = new Recognition()
      current = { recognition, timer: null, final: '' }
      session.current = current
      recognition.lang = 'es-AR'
      recognition.continuous = true
      recognition.interimResults = true
      recognition.maxAlternatives = 1
      recognition.onstart = () => {
        if (session.current !== current || current.stopping) return
        clearTimeout(current.timer); setPhase('listening')
      }
      recognition.onresult = event => {
        if (session.current !== current) return
        const final = [], partial = []
        // results contains the complete session, including revised interim entries.
        for (const result of Array.from(event.results)) {
          const text = result[0]?.transcript?.trim()
          if (text) (result.isFinal ? final : partial).push(text)
        }
        current.final = final.join(' ')
        if (current.final) setReviewVisible(true)
        setDraft(current.final); setInterim(partial.join(' '))
      }
      recognition.onerror = event => {
        if (session.current !== current) return
        release(current)
        const message = errors[event.error] || 'No se pudo completar el dictado. Podés reintentar o escribir manualmente.'
        setError(message + (current.final ? ' Conservamos las frases reconocidas para que las revises.' : ''))
      }
      recognition.onend = () => {
        if (session.current !== current) return
        session.current = null; clearTimeout(current.timer)
        setPhase('idle'); setInterim('')
        setNotice(current.final ? 'Dictado finalizado. Revisá el borrador antes de añadirlo.' : 'No se reconoció texto final. Podés volver a intentar o escribir manualmente.')
      }
      current.timer = setTimeout(() => {
        if (session.current !== current) return
        release(current); setError('El servicio no inició a tiempo. Revisá el permiso y reintentá, o escribí manualmente.')
      }, 12000)
      recognition.start()
    } catch {
      if (current) release(current)
      else setPhase('idle')
      setError('No se pudo iniciar el dictado. Podés reintentar o escribir manualmente.')
    }
  }

  function stop() {
    const current = session.current
    if (!current || phase === 'stopping') return
    current.stopping = true
    setPhase('stopping'); clearTimeout(current.timer)
    // stop may deliver a final result before end; don't abort immediately.
    current.timer = setTimeout(() => {
      if (session.current !== current) return
      release(current); setError('El servicio tardó en finalizar. Revisá las frases finales; el texto provisional no se añadió.')
    }, 4000)
    try { current.recognition.stop() } catch {
      release(current); setError('No se pudo finalizar el dictado. Revisá las frases finales conservadas.')
    }
  }

  function discard() {
    if (session.current) release(session.current)
    setDraft(''); setReviewVisible(false); setInterim(''); setError(''); setNotice('Dictado descartado. El resumen no cambió.')
  }

  function apply() {
    if (active || disabled || !draft.trim() || tooLong) return
    onApply(combined)
    setDraft(''); setReviewVisible(false); setError(''); setNotice('Texto añadido al resumen. Revisalo y guardá el paciente para conservarlo.')
  }

  return <section className="clinical-dictation" aria-labelledby={`${id}-title`}>
    <div className="dictation-heading"><Mic size={18} aria-hidden="true" /><h3 id={`${id}-title`}>Dictar resumen clínico</h3><span>Opcional · Español</span></div>
    <p className="patient-help" id={`${id}-help`}>Dictá el resumen, revisá el texto y añadilo a la historia clínica. También podés escribirlo o corregirlo manualmente.</p>
    {(!Recognition || !secure) && <p className="dictation-warning">{!secure ? 'El micrófono requiere HTTPS o localhost.' : 'Este navegador no dispone de reconocimiento de voz.'} Podés escribir manualmente el resumen.</p>}
    <div className="dictation-actions">
      <button type="button" className="patient-secondary" onClick={start} disabled={disabled || !Recognition || !secure || active || Boolean(draft.trim())} aria-describedby={`${id}-help`}><Mic size={16} aria-hidden="true" />Iniciar dictado</button>
      {active && <button type="button" className="patient-secondary" onClick={stop} disabled={phase === 'stopping'}><Square size={15} aria-hidden="true" />Detener dictado</button>}
      {(active || draft || interim || reviewVisible) && <button type="button" className="patient-secondary" onClick={discard} disabled={disabled}><X size={16} aria-hidden="true" />Descartar dictado</button>}
    </div>
    <p role="status" className="dictation-status">{phase === 'starting' ? 'Esperando permiso e inicio del micrófono…' : phase === 'listening' ? 'Escuchando… Podés detener el dictado cuando termines.' : phase === 'stopping' ? 'Finalizando el reconocimiento…' : notice}</p>
    {error && <p role="alert" className="patient-error">{error}</p>}
    {interim && <p className="dictation-interim"><strong>Vista provisional (no se guarda):</strong> {interim}</p>}
    {(active || reviewVisible) && <div className="dictation-review">
      <label htmlFor={`${id}-draft`}>Borrador de dictado para revisar</label>
      <textarea id={`${id}-draft`} rows={4} value={draft} disabled={active || disabled} onChange={event => setDraft(event.target.value)} aria-describedby={`${id}-review-help`} />
      <p id={`${id}-review-help`} className="patient-help">Corregí nombres, cifras y términos. Añadir conserva el resumen actual y agrega el borrador al final. No guarda el paciente automáticamente.</p>
      {tooLong && <p role="alert" className="patient-error">El resumen combinado supera 20.000 caracteres. Acortá el borrador o el resumen; no se recortará texto automáticamente.</p>}
      <button type="button" className="patient-secondary" onClick={apply} disabled={active || disabled || !draft.trim() || tooLong}><Plus size={16} aria-hidden="true" />Añadir al resumen</button>
    </div>}
  </section>
}
