import { useEffect, useState } from 'react'
import { FlaskConical } from 'lucide-react'
import ClinicalLayout from '../../../components/layout/ClinicalLayout.jsx'
import { errorMessage } from '../../../services/api.js'
import { dateLabel, timeLabel } from '../turnos/fecha.js'
import { listWaitingStudies, simulateNotice } from './api.js'
import '../turnos/turnos.css'

export default function SimularAviso({ session }) {
  const [studies, setStudies] = useState(null)
  const [loadError, setLoadError] = useState('')
  const [off, setOff] = useState(false)
  const [reload, setReload] = useState(0)
  const [studyCode, setStudyCode] = useState('')
  const [volume, setVolume] = useState('')
  const [sending, setSending] = useState(false)
  const [result, setResult] = useState(null)
  const [sendError, setSendError] = useState('')

  useEffect(() => {
    let active = true
    listWaitingStudies().then((data) => { if (active) setStudies(data) })
      .catch((failure) => {
        if (!active) return
        setOff(failure.response?.status === 404)
        setLoadError(failure.response?.status === 404 ? 'El simulador está apagado en este servidor.' : errorMessage(failure))
      })
    return () => { active = false }
  }, [reload])

  async function send(event) {
    event.preventDefault()
    setSending(true); setSendError(''); setResult(null)
    try {
      setResult({ code: studyCode, ...await simulateNotice(studyCode, volume) })
      // El estudio avisado ya no tiene turno reservado: sale de la lista.
      setStudyCode(''); setVolume(''); setReload((n) => n + 1)
    } catch (failure) {
      setSendError(errorMessage(failure))
    } finally {
      setSending(false)
    }
  }

  return <ClinicalLayout session={session}><section className="turnos-page turnos-patient">
    <header className="turnos-heading"><span className="turnos-badge turnos-badge-alert">SIMULACIÓN</span>
      <h1><FlaskConical aria-hidden="true" />Simular aviso del bot</h1>
      <p>Hace lo mismo que el aviso real del bot de extracción: registra la muestra, cierra el turno y, si el volumen
        no alcanza, avisa por mail que hay que repetir la extracción. Solo para demo y pruebas.</p></header>
    {result && <div role="status" className={result.sample_status === 'ready_for_pickup' ? 'turnos-note' : 'turnos-resample'}>
      {result.sample_status === 'ready_for_pickup'
        ? <p><strong>Muestra lista para retirar.</strong> El estudio {result.code} espera al transportista.</p>
        : <p><strong>Hay que repetir la extracción.</strong> La muestra del estudio {result.code} no alcanzó (mínimo 2 ml);
          se le avisa por mail al paciente para que saque un turno nuevo.</p>}
    </div>}
    {loadError ? <div role="alert" className="turnos-error"><p>{loadError}</p>
      {!off && <button type="button" onClick={() => { setLoadError(''); setReload((n) => n + 1) }}>Reintentar</button>}</div>
      : !studies ? <p role="status" className="turnos-loading">Cargando turnos reservados...</p>
        : studies.length === 0 ? <div className="turnos-card"><p className="turnos-empty">No hay turnos reservados esperando el aviso.</p></div>
          : <form className="turnos-card" onSubmit={send}>
            <label htmlFor="simulador-study">Estudio con turno reservado</label>
            <select id="simulador-study" value={studyCode} onChange={(event) => setStudyCode(event.target.value)} required>
              <option value="">Elegí un estudio</option>
              {studies.map((study) => <option key={study.study_id} value={study.code}>
                {study.code} · {study.patient_name} · {study.center_name}, {dateLabel(study.starts_at)} {timeLabel(study.starts_at)}
              </option>)}
            </select>
            <label htmlFor="simulador-volume">Volumen extraído (ml)</label>
            <input id="simulador-volume" type="number" inputMode="decimal" min="0.01" max="999.99" step="any"
              value={volume} onChange={(event) => setVolume(event.target.value)} required />
            {sendError && <div role="alert" className="turnos-error"><p>{sendError}</p></div>}
            <div className="turnos-links">
              <button type="submit" className="turnos-action" disabled={sending || !studyCode || !volume}>
                {sending ? 'Enviando...' : 'Enviar aviso'}</button>
            </div>
          </form>}
  </section></ClinicalLayout>
}
