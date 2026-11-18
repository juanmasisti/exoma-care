import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { CalendarCheck } from 'lucide-react'
import ClinicalLayout from '../../../components/layout/ClinicalLayout.jsx'
import { errorMessage } from '../../../services/api.js'
import { listMyAppointments, listMyTrackings } from './api.js'
import { STAGES, stageTitle } from './etapas.js'
import { dateLabel, timeLabel } from './fecha.js'
import './turnos.css'

export default function MisTurnos({ session }) {
  const [appointments, setAppointments] = useState(null)
  const [error, setError] = useState('')
  const [retry, setRetry] = useState(0)

  useEffect(() => {
    let active = true
    listMyAppointments().then((data) => { if (active) setAppointments(data) })
      .catch((failure) => { if (active) setError(errorMessage(failure)) })
    return () => { active = false }
  }, [retry])

  const trackings = useTrackings()
  const trackingOf = (studyId) => trackings.data?.find((study) => study.study_id === studyId)
  // Una tarjeta por estudio: el que tiene turno reservado ya aparece arriba, con su etapa.
  // Hasta que carguen los turnos no se muestra: si no, una tarjeta aparecería y se iría.
  const tracked = !appointments && !error ? [] : trackings.data?.filter((study) => !appointments?.some((appointment) => appointment.study_id === study.study_id)) ?? []
  return <ClinicalLayout session={session}><section className="turnos-page turnos-patient">
    <header className="turnos-heading"><span>PORTAL DEL PACIENTE</span><h1><CalendarCheck aria-hidden="true" />Mis turnos</h1>
      <p>Tus turnos de extracción reservados y el seguimiento de tus estudios.</p></header>
    {error ? <div role="alert" className="turnos-error"><p>{error}</p><button type="button" onClick={() => { setError(''); setRetry((n) => n + 1) }}>Reintentar</button></div>
      : !appointments ? <p role="status" className="turnos-loading">Cargando turnos...</p>
        // Con estudios en seguimiento no se invita a reservar: lo normal después de la extracción es no tener turno.
        : appointments.length === 0 ? tracked.length === 0 && <div className="turnos-card turnos-appointment"><p className="turnos-empty">No tenés turnos reservados.</p>
          <Link className="turnos-action" to="/paciente/turnos/reservar">Reservar turno</Link></div>
          : <ul className="turnos-list">{appointments.map((appointment) => <li key={appointment.id} className="turnos-card turnos-appointment">
            <h2>Estudio {appointment.study_code}</h2>
            <span className="turnos-badge">Turno reservado</span>
            <StageBar stage={trackingOf(appointment.study_id)?.stage ?? 'extraction'} />
            <dl>
              <dt>Fecha</dt><dd>{dateLabel(appointment.starts_at)}</dd>
              <dt>Hora</dt><dd>{timeLabel(appointment.starts_at)}</dd>
              <dt>Centro</dt><dd>{appointment.center.name}<small>{appointment.center.address}, {appointment.center.city}</small></dd>
            </dl>
            {/* Botón principal según el momento: con turno reservado, el turno (orden y consentimiento). */}
            <div className="turnos-links">
              <Link className="turnos-action" to={`/paciente/estudios/${appointment.study_id}/turno`}>Ver turno</Link>
              <Link className="turnos-action-secondary" to={`/paciente/estudios/${appointment.study_id}/seguimiento`}>Ver seguimiento</Link>
            </div>
          </li>)}</ul>}
    {trackings.error ? <div role="alert" className="turnos-error turnos-tracked"><p>{trackings.error}</p><button type="button" onClick={trackings.reload}>Reintentar</button></div>
      : tracked.length > 0 && <section className="turnos-tracked" aria-labelledby="turnos-tracked-title">
        <h2 id="turnos-tracked-title">Seguimiento de tus estudios</h2>
        <ul className="turnos-list">{tracked.map((study) => <li key={study.study_id} className="turnos-card turnos-appointment">
          <h3>Estudio {study.code}</h3><span className={study.requires_new_extraction ? 'turnos-badge turnos-badge-alert' : 'turnos-badge'}>{stageTitle(study.stage)}</span>
          {!study.requires_new_extraction && <StageBar stage={study.stage} />}
          <div className="turnos-links">
            {study.requires_new_extraction && <Link className="turnos-action" to={`/paciente/turnos/reservar?estudio=${study.study_id}`}>Sacar turno nuevo</Link>}
            <Link className={study.requires_new_extraction ? 'turnos-action-secondary' : 'turnos-action'} to={`/paciente/estudios/${study.study_id}/seguimiento`}>Ver seguimiento</Link>
          </div>
        </li>)}</ul>
      </section>}
  </section></ClinicalLayout>
}

// Mini barra con las etapas de etapas.js: para lector de pantalla es una imagen cuyo texto dice cuál es la actual.
function StageBar({ stage }) {
  const current = STAGES.findIndex(([key]) => key === stage)
  return <ol className="turnos-minibar" role="img" aria-label={`Etapa ${current + 1} de ${STAGES.length}: ${stageTitle(stage)}`}>
    {STAGES.map(([key], index) => <li key={key} className={index < current ? 'done' : index === current ? 'current' : ''} />)}
  </ol>
}

// Estudios ya extraídos (el turno dejó de estar reservado). Carga y error aparte: si falla, la lista de turnos sigue.
function useTrackings() {
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const [retry, setRetry] = useState(0)
  useEffect(() => {
    let active = true
    listMyTrackings().then((result) => { if (active) setData(result) })
      .catch((failure) => { if (active) setError(errorMessage(failure)) })
    return () => { active = false }
  }, [retry])
  return { data, error, reload: () => { setError(''); setRetry((n) => n + 1) } }
}
