import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import ClinicalLayout from '../../../components/layout/ClinicalLayout.jsx'
import { errorMessage } from '../../../services/api.js'
import { getStudyTracking } from './api.js'
import { STAGES, stageTitle } from './etapas.js'
import { dateLabel } from './fecha.js'
import './turnos.css'

// Motivo del último descarte: el que cargó bioinformática (siempre lo exige) o, si no hay, la muestra
// nació descartada por volumen (regla de 2 ml del back, MIN_SAMPLE_VOLUME_ML).
function resampleReason(samples) {
  const discarded = samples.filter((sample) => sample.status === 'discarded').at(-1)
  const reason = discarded?.events.findLast((event) => event.to_status === 'discarded')?.reason
  return reason || 'La muestra no alcanzó el volumen mínimo de 2 ml.'
}

export default function Seguimiento({ session }) {
  const { studyId } = useParams()
  const [tracking, setTracking] = useState(null)
  const [error, setError] = useState('')
  const [retry, setRetry] = useState(0)

  useEffect(() => {
    let active = true
    getStudyTracking(studyId).then((data) => { if (active) setTracking(data) })
      .catch((failure) => { if (active) setError(errorMessage(failure)) })
    return () => { active = false }
  }, [studyId, retry])

  const current = STAGES.findIndex(([key]) => key === tracking?.stage)
  const history = tracking?.samples.filter((sample) => sample.status === 'discarded') ?? []
  return <ClinicalLayout session={session} pageLabel="Seguimiento"><section className="turnos-page">
    <header className="turnos-header"><h1>Seguimiento</h1><p>En qué etapa está tu estudio y tu muestra.</p></header>
    {error ? <div role="alert" className="turnos-error"><p>{error}</p><button type="button" onClick={() => { setError(''); setRetry((n) => n + 1) }}>Reintentar</button></div>
      : !tracking ? <p role="status" className="turnos-loading">Cargando seguimiento...</p>
        : <article className="turnos-card turnos-appointment" aria-labelledby="turnos-tracking-title">
          <h2 id="turnos-tracking-title">Estudio {tracking.code}: {stageTitle(tracking.stage)}</h2>
          {tracking.requires_new_extraction ? <div className="turnos-resample">
            <p>La muestra no sirvió para el análisis y hay que tomar una nueva. Es el mismo estudio: no tenés que pagar de nuevo.</p>
            <p><strong>Motivo:</strong> {resampleReason(tracking.samples)}</p>
            <Link className="turnos-primary-link" to={`/paciente/turnos/reservar?estudio=${tracking.study_id}`}>Sacar turno nuevo</Link>
          </div>
            : <ol className="turnos-stages">{STAGES.map(([key, title, detail], index) =>
              <li key={key} className={index < current ? 'done' : index === current ? 'current' : 'pending'}
                aria-current={index === current ? 'step' : undefined}>
                <strong>{title}</strong>
                {index !== current && <span className="turnos-sr-only">{index < current ? ' (hecha)' : ' (por venir)'}</span>}
                {index === current && <small>{detail}</small>}
              </li>)}</ol>}
          {history.length > 0 && <section className="turnos-history" aria-labelledby="turnos-history-title">
            <h3 id="turnos-history-title">Muestras anteriores</h3>
            <ul>{history.map((sample) => <li key={sample.id}>
              {dateLabel(sample.events[0].at)}: {String(sample.volume_ml).replace('.', ',')} ml, descartada
            </li>)}</ul>
          </section>}
        </article>}
  </section></ClinicalLayout>
}
