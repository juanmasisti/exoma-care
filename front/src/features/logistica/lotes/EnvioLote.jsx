import { useEffect, useState } from 'react'
import { api, errorMessage } from '../../../services/api.js'
import { dateLabel, timeLabel } from '../turnos/fecha.js'

// Envío del lote (T06, decisión 019): autorización del Ministerio (simulado), CSV, PDF y retiro de FedEx.
// Props: session, sampleSetId y onChange() para avisarle al detalle del lote que lo recargue.
const STATUS_LABELS = {
  assembling: 'Armándose',
  closed: 'Cerrado',
  awaiting_pickup: 'Esperando el retiro de FedEx',
  in_transit_to_sequencing_lab: 'En viaje al laboratorio de secuenciación',
}
// turnos.css solo le da estilo al input numérico; este es igual.
const INPUT_STYLE = { boxSizing: 'border-box', width: '100%', maxWidth: 240, border: '1px solid #cbd5e1', borderRadius: 7,
  padding: '10px 12px', font: 'inherit', fontSize: 12, color: '#0f172a', minHeight: 41, background: '#fff' }

// Por axios y no con un link: el token viaja en el header Authorization.
async function downloadFile(url, fileName) {
  let blob
  try {
    blob = (await api.get(url, { responseType: 'blob' })).data
  } catch (failure) {
    // Con responseType blob el error también llega como Blob: se lee para que errorMessage muestre el detail.
    const body = failure.response?.data
    if (body instanceof Blob) {
      try { failure.response.data = JSON.parse(await body.text()) } catch { /* sin detail: queda el mensaje genérico */ }
    }
    throw failure
  }
  const href = URL.createObjectURL(blob)
  const link = Object.assign(document.createElement('a'), { href, download: fileName })
  document.body.append(link); link.click(); link.remove()
  setTimeout(() => URL.revokeObjectURL(href), 0)
}

export default function EnvioLote({ sampleSetId, onChange }) {
  const [shipment, setShipment] = useState(null)
  const [loadError, setLoadError] = useState('')
  const [reload, setReload] = useState(0)
  const [busy, setBusy] = useState(null)
  const [actionError, setActionError] = useState('')
  const [scheduledAt, setScheduledAt] = useState('')
  const base = `/shipments/${sampleSetId}`

  useEffect(() => {
    let active = true
    api.get(base).then(({ data }) => { if (active) setShipment(data) })
      .catch((failure) => { if (active) setLoadError(errorMessage(failure)) })
    return () => { active = false }
  }, [base, reload])

  async function run(action, request) {
    setBusy(action); setActionError('')
    try {
      const data = await request()
      if (data) { setShipment(data); onChange?.() }
    } catch (failure) {
      setActionError(errorMessage(failure))
      // Otro pedido cambió el lote: se recarga para no ofrecer lo que ya no corresponde.
      if (failure.response?.status === 409) setReload((n) => n + 1)
    } finally {
      setBusy(null)
    }
  }

  const authorize = () => run('authorization', async () => (await api.post(`${base}/authorization`)).data)
  // Argentina no tiene horario de verano: la hora elegida siempre es -03:00.
  const schedule = (event) => {
    event.preventDefault()
    run('pickup', async () => (await api.post(`${base}/pickup`, { scheduled_at: `${scheduledAt}:00-03:00` })).data)
  }
  const refresh = () => run('refresh', async () => (await api.post(`${base}/refresh`)).data)
  const download = (action, path, fileName) => run(action, () => downloadFile(`${base}/${path}`, fileName))

  // turnos-page y turnos-patient: los estilos de botones, label e input de turnos.css cuelgan de ahí.
  return <section className="turnos-page turnos-patient turnos-card turnos-appointment" aria-label="Envío del lote">
    <h2>Envío</h2>
    {loadError ? <div role="alert" className="turnos-error"><p>{loadError}</p>
      <button type="button" onClick={() => { setLoadError(''); setReload((n) => n + 1) }}>Reintentar</button></div>
      : !shipment ? <p role="status" className="turnos-loading">Cargando envío...</p>
        : shipment.status === 'assembling' ? <p className="turnos-empty">El envío se prepara cuando se cierra el lote.</p>
          : <>
            <dl>
              <dt>Estado</dt><dd>{STATUS_LABELS[shipment.status] ?? shipment.status}</dd>
              <dt>Autorización del Ministerio de Salud</dt>
              <dd>{shipment.has_authorization ? 'Autorizado' : 'Pendiente'}<small>Ministerio SIMULADO</small></dd>
              {shipment.pickup_at && <><dt>Retiro de FedEx</dt>
                <dd>{dateLabel(shipment.pickup_at)}, {timeLabel(shipment.pickup_at)}<small>Laboratorio Central</small></dd></>}
            </dl>
            {!shipment.has_authorization && <>
              <p className="turnos-note">El lote está cerrado y todavía no tiene la autorización del Ministerio de Salud.</p>
              <div className="turnos-links"><button type="button" className="turnos-action" disabled={busy !== null} onClick={authorize}>
                {busy === 'authorization' ? 'Pidiendo...' : 'Pedir autorización'}</button></div>
            </>}
            {(shipment.has_csv || shipment.has_authorization) && <div className="turnos-documents" role="group" aria-label="Archivos del envío">
              {shipment.has_csv && <button type="button" disabled={busy !== null} onClick={() => download('csv', 'csv', `lote-${shipment.id}.csv`)}>
                {busy === 'csv' ? 'Descargando...' : 'Descargar CSV'}</button>}
              {shipment.has_authorization && <button type="button" disabled={busy !== null}
                onClick={() => download('pdf', 'authorization.pdf', `lote-${shipment.id}-autorizacion.pdf`)}>
                {busy === 'pdf' ? 'Descargando...' : 'Descargar autorización'}</button>}
            </div>}
            {shipment.status === 'closed' && shipment.has_authorization && <form onSubmit={schedule}>
              <label htmlFor="envio-retiro">Fecha y hora del retiro</label>
              <input id="envio-retiro" type="datetime-local" style={INPUT_STYLE} value={scheduledAt}
                onChange={(event) => setScheduledAt(event.target.value)} required />
              <p className="turnos-note">FedEx retira en el Laboratorio Central en días hábiles, de 9 a 18 h.</p>
              <div className="turnos-links"><button type="submit" className="turnos-action" disabled={busy !== null || !scheduledAt}>
                {busy === 'pickup' ? 'Programando...' : 'Programar retiro'}</button></div>
            </form>}
            {shipment.status === 'awaiting_pickup' && <>
              <p className="turnos-note">FedEx no avisa cuando retira: consultá el estado.</p>
              <div className="turnos-links"><button type="button" disabled={busy !== null} onClick={refresh}>
                {busy === 'refresh' ? 'Consultando...' : 'Actualizar estado'}</button></div>
            </>}
          </>}
    {actionError && <div role="alert" className="turnos-error"><p>{actionError}</p></div>}
  </section>
}
