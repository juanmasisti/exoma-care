import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import ClinicalLayout from '../../../components/layout/ClinicalLayout.jsx'
import { errorMessage } from '../../../services/api.js'
import { cancelAppointment, downloadAppointmentDocument, getStudyAppointment } from './api.js'
import { dateLabel, timeLabel } from './fecha.js'
import './turnos.css'

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
  const [downloading, setDownloading] = useState(null)
  const [downloadError, setDownloadError] = useState('')
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

  async function download(kind, fileName) {
    setDownloading(kind); setDownloadError('')
    try {
      const url = URL.createObjectURL(await downloadAppointmentDocument(appointment.id, kind))
      const link = Object.assign(document.createElement('a'), { href: url, download: `${fileName}-${appointment.study_code}.pdf` })
      document.body.append(link); link.click(); link.remove()
      // Se libera después del click: revocarla en el mismo paso puede cortar la descarga en algunos navegadores.
      setTimeout(() => URL.revokeObjectURL(url), 0)
    } catch (failure) {
      setDownloadError(errorMessage(failure))
    } finally {
      setDownloading(null)
    }
  }

  const center = appointment?.center
  return <ClinicalLayout session={session} pageLabel="Día de extracción"><section className="turnos-page">
    <header className="turnos-header"><h1>Día de extracción</h1><p>Tu turno para la extracción de sangre del estudio.</p></header>

    {loadError ? <div role="alert" className="turnos-error"><p>{loadError}</p><button type="button" onClick={() => { setLoadError(''); setRetry((n) => n + 1) }}>Reintentar</button></div>
      : missing ? <div className="turnos-card turnos-appointment"><p className="turnos-empty">Este estudio no tiene un turno vigente.</p><Link to={bookingPath}>Reservar turno</Link></div>
        : !appointment ? <p role="status" className="turnos-loading">Cargando turno...</p>
          : <article className="turnos-card turnos-appointment" aria-labelledby="turnos-appointment-title">
            <h2 id="turnos-appointment-title">Tu turno</h2>
            <dl>
              <dt>Fecha</dt><dd>{dateLabel(appointment.starts_at)}</dd>
              <dt>Hora</dt><dd>{timeLabel(appointment.starts_at)}</dd>
              <dt>Centro</dt><dd>{center.name}<small>{center.address}, {center.city}</small>{center.phone && <small>Teléfono: {center.phone}</small>}</dd>
            </dl>
            <p className="turnos-note">No requiere ayuno ni preparación especial.</p>
            <div className="turnos-documents" role="group" aria-label="Documentos del turno">
              <button type="button" disabled={downloading !== null} onClick={() => download('order', 'orden')}>{downloading === 'order' ? 'Descargando...' : 'Descargar orden'}</button>
              <button type="button" disabled={downloading !== null} onClick={() => download('consent', 'consentimiento')}>{downloading === 'consent' ? 'Descargando...' : 'Descargar consentimiento'}</button>
              <p>Imprimí el consentimiento, firmalo y entregalo en papel.</p>
            </div>
            {downloadError && <div role="alert" className="turnos-error"><p>{downloadError}</p></div>}
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
