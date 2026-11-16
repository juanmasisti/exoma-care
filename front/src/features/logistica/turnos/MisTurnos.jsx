import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import ClinicalLayout from '../../../components/layout/ClinicalLayout.jsx'
import { errorMessage } from '../../../services/api.js'
import { listMyAppointments, listMyTrackings } from './api.js'
import { stageTitle } from './etapas.js'
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
  const tracked = trackings.data?.length > 0
  return <ClinicalLayout session={session}><section className="turnos-page">
    <header className="turnos-header"><h1>Mis turnos</h1><p>Tus turnos de extracción reservados y el seguimiento de tus estudios.</p></header>
    {error ? <div role="alert" className="turnos-error"><p>{error}</p><button type="button" onClick={() => { setError(''); setRetry((n) => n + 1) }}>Reintentar</button></div>
      : !appointments ? <p role="status" className="turnos-loading">Cargando turnos...</p>
        // Con estudios en seguimiento no se invita a reservar: lo normal después de la extracción es no tener turno.
        : appointments.length === 0 ? !tracked && <div className="turnos-card turnos-appointment"><p className="turnos-empty">No tenés turnos reservados.</p><Link to="/paciente/turnos/reservar">Reservar turno</Link></div>
          : <ul className="turnos-list">{appointments.map((appointment) => <li key={appointment.id} className="turnos-card turnos-appointment">
            <h2>Estudio {appointment.study_code}</h2>
            <dl>
              <dt>Fecha</dt><dd>{dateLabel(appointment.starts_at)}</dd>
              <dt>Hora</dt><dd>{timeLabel(appointment.starts_at)}</dd>
              <dt>Centro</dt><dd>{appointment.center.name}<small>{appointment.center.address}, {appointment.center.city}</small></dd>
            </dl>
            <div className="turnos-links">
              <Link to={`/paciente/estudios/${appointment.study_id}/turno`}>Ver turno</Link>
              <Link to={`/paciente/estudios/${appointment.study_id}/seguimiento`}>Ver seguimiento</Link>
            </div>
          </li>)}</ul>}
    {trackings.error ? <div role="alert" className="turnos-error turnos-tracked"><p>{trackings.error}</p><button type="button" onClick={trackings.reload}>Reintentar</button></div>
      : tracked && <section className="turnos-tracked" aria-labelledby="turnos-tracked-title">
        <h2 id="turnos-tracked-title">Seguimiento de tus estudios</h2>
        <ul className="turnos-list">{trackings.data.map((study) => <li key={study.study_id} className="turnos-card turnos-appointment">
          <h3>Estudio {study.code}</h3><p>{stageTitle(study.stage)}</p>
          <Link to={`/paciente/estudios/${study.study_id}/seguimiento`}>Ver seguimiento</Link>
        </li>)}</ul>
      </section>}
  </section></ClinicalLayout>
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
