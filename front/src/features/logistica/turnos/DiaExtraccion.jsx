import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import ClinicalLayout from '../../../components/layout/ClinicalLayout.jsx'
import { errorMessage } from '../../../services/api.js'
import { cancelAppointment, getStudyAppointment } from './api.js'
import './turnos.css'

// Fecha y hora salen del ISO del back, que ya viene en hora de Argentina; así no dependen de la zona del navegador.
function dateLabel(iso) {
  const [year, month, day] = iso.slice(0, 10).split('-').map(Number)
  return new Date(year, month - 1, day).toLocaleDateString('es-AR', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' })
}

export default function DiaExtraccion({ session }) {
  const { studyId } = useParams()
  const navigate = useNavigate()
  const [appointment, setAppointment] = useState(null)
  const [started, setStarted] = useState(false)
  const [missing, setMissing] = useState(false)
  const [loadError, setLoadError] = useState('')
  const [retry, setRetry] = useState(0)
  const [confirming, setConfirming] = useState(false)
  const [cancelling, setCancelling] = useState(false)
  const [cancelError, setCancelError] = useState('')
  const bookingPath = `/paciente/turnos/reservar?estudio=${studyId}`

  useEffect(() => {
    let active = true
    getStudyAppointment(studyId).then((data) => {
      if (!active) return
      setAppointment(data)
      // El back decide con su reloj; acá solo se evita ofrecer una cancelación que va a rechazar.
      setStarted(new Date(data.starts_at).getTime() <= Date.now())
    })
      .catch((failure) => {
        if (!active) return
        if (failure.response?.status === 404) setMissing(true)
        else setLoadError(errorMessage(failure))
      })
    return () => { active = false }
  }, [studyId, retry])

  async function cancel() {
    setCancelling(true); setCancelError('')
    try {
      await cancelAppointment(appointment.id)
      navigate(bookingPath)
    } catch (failure) {
      setCancelling(false)
      setCancelError(errorMessage(failure))
      // El back no deja cancelar (ya empezó o el estudio avanzó): no se vuelve a ofrecer lo mismo y se recarga el turno.
      if (failure.response?.status === 409) { setConfirming(false); setRetry((n) => n + 1) }
    }
  }

  const center = appointment?.center
  return <ClinicalLayout session={session}><section className="turnos-page">
    <header className="turnos-header"><h1>Día de extracción</h1><p>Tu turno para la extracción de sangre del estudio.</p></header>

    {loadError ? <div role="alert" className="turnos-error"><p>{loadError}</p><button type="button" onClick={() => { setLoadError(''); setRetry((n) => n + 1) }}>Reintentar</button></div>
      : missing ? <div className="turnos-card turnos-appointment"><p className="turnos-empty">Este estudio no tiene un turno vigente.</p><Link to={bookingPath}>Reservar turno</Link></div>
        : !appointment ? <p role="status" className="turnos-loading">Cargando turno...</p>
          : <article className="turnos-card turnos-appointment" aria-labelledby="turnos-appointment-title">
            <h2 id="turnos-appointment-title">Tu turno</h2>
            <dl>
              <dt>Fecha</dt><dd>{dateLabel(appointment.starts_at)}</dd>
              <dt>Hora</dt><dd>{appointment.starts_at.slice(11, 16)} h</dd>
              <dt>Centro</dt><dd>{center.name}<small>{center.address}, {center.city}</small>{center.phone && <small>Teléfono: {center.phone}</small>}</dd>
            </dl>
            <p className="turnos-note">No requiere ayuno ni preparación especial.</p>
            {cancelError && <div role="alert" className="turnos-error"><p>{cancelError}</p></div>}
            {started ? <p className="turnos-note">El turno ya empezó: no se puede cancelar.</p>
              : !confirming ? <button type="button" onClick={() => setConfirming(true)}>Cancelar turno</button>
              : <div className="turnos-confirm" role="group" aria-labelledby="turnos-confirm-question">
                <p id="turnos-confirm-question">¿Querés cancelar este turno? El horario queda libre para otra persona.</p>
                <button type="button" className="turnos-danger" disabled={cancelling} onClick={cancel}>{cancelling ? 'Cancelando...' : 'Sí, cancelar turno'}</button>
                <button type="button" disabled={cancelling} onClick={() => setConfirming(false)}>No, mantener turno</button>
              </div>}
          </article>}
  </section></ClinicalLayout>
}
