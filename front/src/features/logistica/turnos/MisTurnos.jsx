import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import ClinicalLayout from '../../../components/layout/ClinicalLayout.jsx'
import { errorMessage } from '../../../services/api.js'
import { listMyAppointments } from './api.js'
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

  return <ClinicalLayout session={session}><section className="turnos-page">
    <header className="turnos-header"><h1>Mis turnos</h1><p>Tus turnos de extracción reservados.</p></header>
    {error ? <div role="alert" className="turnos-error"><p>{error}</p><button type="button" onClick={() => { setError(''); setRetry((n) => n + 1) }}>Reintentar</button></div>
      : !appointments ? <p role="status" className="turnos-loading">Cargando turnos...</p>
        : appointments.length === 0 ? <div className="turnos-card turnos-appointment"><p className="turnos-empty">No tenés turnos reservados.</p><Link to="/paciente/turnos/reservar">Reservar turno</Link></div>
          : <ul className="turnos-list">{appointments.map((appointment) => <li key={appointment.id} className="turnos-card turnos-appointment">
            <h2>Estudio {appointment.study_code}</h2>
            <dl>
              <dt>Fecha</dt><dd>{dateLabel(appointment.starts_at)}</dd>
              <dt>Hora</dt><dd>{timeLabel(appointment.starts_at)}</dd>
              <dt>Centro</dt><dd>{appointment.center.name}<small>{appointment.center.address}, {appointment.center.city}</small></dd>
            </dl>
            <Link to={`/paciente/estudios/${appointment.study_id}/turno`}>Ver turno</Link>
          </li>)}</ul>}
  </section></ClinicalLayout>
}
