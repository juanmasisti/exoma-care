import { useEffect, useRef, useState } from 'react'
import { Link, Navigate, Route, Routes, useParams } from 'react-router-dom'
import { CheckCircle2, MapPin, PackageCheck, Truck } from 'lucide-react'
import ClinicalLayout from '../../../components/layout/ClinicalLayout.jsx'
import { errorMessage } from '../../../services/api.js'
import { dateLabel, timeLabel } from '../turnos/fecha.js'
import { getMyRoute, listDailyRoutes, pickUp, registerArrival, today } from './api.js'
import RecorridoMap from './RecorridoMap.jsx'
import '../turnos/turnos.css'
import './transportista.css'

// P1 inicio, P2 orden, P3 centro (P4 confirmar y P5 comprobante), P6 a bordo (P7 fin, P8 confirmar y P9 llegada).
// La orden se carga una vez acá y la comparten todas las pantallas; cada acción la vuelve a pedir.
export default function Transportista({ session }) {
  const [provinceId, setProvinceId] = useState('')
  const [route, setRoute] = useState(null)  // null: cargando; false: no hay orden
  const [error, setError] = useState('')
  const [retry, setRetry] = useState(0)
  const date = today()

  useEffect(() => {
    if (!provinceId) return undefined
    let active = true
    getMyRoute(date, provinceId).then((data) => { if (active) setRoute(data) })
      .catch((failure) => {
        if (!active) return
        if (failure.response?.status === 404) setRoute(false)
        else setError(errorMessage(failure))
      })
    return () => { active = false }
  }, [date, provinceId, retry])

  function chooseProvince(value) { setProvinceId(value); setRoute(null); setError('') }
  const reload = () => { setError(''); setRetry((n) => n + 1) }
  // Sin orden cargada, las pantallas internas vuelven al inicio a elegir la provincia.
  const guard = (page) => route ? page : <Navigate to="/transporte" replace />

  return <ClinicalLayout session={session}><section className="turnos-page turnos-patient transporte">
    {/* En todas las pantallas: si falla la recarga después de un retiro, no se sigue con la orden vieja sin avisar. */}
    {error && <div role="alert" className="turnos-error transporte-result"><p>{error}</p><button type="button" onClick={reload}>Reintentar</button></div>}
    <Routes>
      <Route index element={<Inicio date={date} provinceId={provinceId} onProvince={chooseProvince} route={route} error={error} />} />
      <Route path="orden" element={guard(<Orden route={route} />)} />
      <Route path="centro/:stopId" element={guard(<Centro route={route} onChanged={reload} />)} />
      <Route path="a-bordo" element={guard(<ABordo route={route} onChanged={reload} />)} />
      <Route path="*" element={<Navigate to="/transporte" replace />} />
    </Routes>
  </section></ClinicalLayout>
}

function Heading({ title, children }) {
  return <header className="turnos-heading"><span>TRANSPORTE</span><h1><Truck aria-hidden="true" />{title}</h1>{children}</header>
}

const pickedStops = (route) => route.stops.filter((stop) => stop.picked_up_at)
const nextStop = (route) => route.stops.find((stop) => stop.id === route.next_stop_id)
const count = (n, one, many) => `${n} ${n === 1 ? one : many}`
const samples = (n) => count(n, 'muestra', 'muestras')
// La extracción puede ser de otro día: fecha corta y hora, o "—" si el aviso no la trajo.
const takenLabel = (iso) => iso ? `${iso.slice(8, 10)}/${iso.slice(5, 7)} ${timeLabel(iso)}` : '—'
const volumeLabel = (ml) => `${Number(ml).toLocaleString('es-AR')} ml`

function Progress({ route }) {
  const done = pickedStops(route).length
  return <div className="turnos-card transporte-avance">
    <div><strong>Avance del recorrido</strong><span>{done} de {count(route.stops.length, 'centro retirado', 'centros retirados')}</span></div>
    <progress value={done} max={route.stops.length} aria-label="Avance del recorrido" />
  </div>
}

// P1: provincia (PROVISORIO hasta el rol transportista con provincia), indicadores, avance y siguiente centro.
function Inicio({ date, provinceId, onProvince, route, error }) {
  const [provinces, setProvinces] = useState(null)
  const [provincesError, setProvincesError] = useState('')
  // Las provincias salen de las órdenes de hoy: /provinces es del turnero y solo lo usa el paciente.
  useEffect(() => {
    let active = true
    listDailyRoutes(date).then((routes) => {
      if (active) setProvinces(routes.map((item) => ({ id: item.province_id, name: item.province })))
    }).catch((failure) => { if (active) setProvincesError(errorMessage(failure)) })
    return () => { active = false }
  }, [date])

  const next = route && nextStop(route)
  const toPickUp = route ? route.stops.filter((stop) => !stop.picked_up_at).reduce((total, stop) => total + stop.samples.length, 0) : 0
  return <>
    <Heading title="Tu recorrido de hoy"><p>{dateLabel(date)}. Retirá en el orden fijo y llevá las muestras al Laboratorio Central.</p></Heading>
    <div className="turnos-card transporte-block">
      <label htmlFor="transporte-province">Provincia (PROVISORIO: después sale de tu usuario)</label>
      {provincesError ? <p role="alert" className="turnos-error">{provincesError}</p>
        : provinces?.length === 0 ? <p className="turnos-empty">Hoy no hay órdenes del día generadas.</p>
        : <select id="transporte-province" value={provinceId} onChange={(event) => onProvince(event.target.value)} disabled={!provinces}>
          <option value="">{provinces ? 'Elegí tu provincia' : 'Cargando provincias...'}</option>
          {provinces?.map((province) => <option key={province.id} value={province.id}>{province.name}</option>)}
        </select>}
    </div>
    {!provinceId ? null
      : route === null ? !error && <p role="status" className="turnos-loading">Cargando la orden del día...</p>
          : route === false ? <div className="turnos-card"><p className="turnos-empty">No hay orden del día para tu provincia hoy.</p></div>
            : <>
              <ul className="transporte-kpis" aria-label="Resumen del recorrido">
                <li><strong>{route.stops.length - pickedStops(route).length}</strong>Centros pendientes</li>
                <li><strong>{pickedStops(route).length}</strong>Centros retirados</li>
                <li><strong>{toPickUp}</strong>Muestras para retirar</li>
                <li className="transporte-kpi-accent"><strong>{route.on_board.length}</strong>Muestras a bordo</li>
              </ul>
              <Progress route={route} />
              <div className="turnos-card transporte-next-card">
                {route.status === 'arrived' ? <><h2>Recorrido terminado</h2>
                  <p className="transporte-text">Llegada al Laboratorio Central registrada a las {timeLabel(route.arrived_at)}.</p></>
                  : next ? <><h2>Siguiente centro</h2><span className="turnos-badge">Parada {next.sequence} de {route.stops.length}</span>
                    <p className="transporte-text"><strong>{next.center.name}</strong><small>{next.center.address}, {next.center.city} · {samples(next.samples.length)}</small></p></>
                    : <><h2>Retiraste todos los centros</h2><p className="transporte-text">Registrá la llegada al Laboratorio Central.</p></>}
                {route.status === 'pending' && (next
                  ? <Link className="turnos-action transporte-primary" to={`/transporte/centro/${next.id}`}>Ir al centro</Link>
                  : <Link className="turnos-action transporte-primary" to="/transporte/a-bordo">Registrar llegada</Link>)}
                <div className="turnos-links">
                  <Link className="turnos-action-secondary" to="/transporte/orden">Ver orden completa</Link>
                  <Link className="turnos-action-secondary" to="/transporte/a-bordo">Muestras a bordo</Link>
                </div>
              </div>
            </>}
  </>
}

// P2: línea de paradas en la secuencia de la API de recorridos y mapa del recorrido; solo la siguiente se puede abrir.
function Orden({ route }) {
  return <>
    <Heading title={`Orden del día · ${route.province}`}><p>El orden es fijo: no se puede cambiar ni saltear un centro.</p></Heading>
    <Progress route={route} />
    <div className="transporte-orden">
      <ol className="transporte-timeline" aria-label="Paradas del recorrido">{route.stops.map((stop) => {
        const isNext = stop.id === route.next_stop_id
        const state = stop.picked_up_at ? 'done' : isNext ? 'next' : 'pending'
        return <li key={stop.id} className={`transporte-stop transporte-stop-${state}`}>
          <span className="transporte-stop-marker" aria-hidden="true">{stop.picked_up_at ? <CheckCircle2 /> : stop.sequence}</span>
          <div className="transporte-stop-body">
            <h2>{stop.sequence}. {stop.center.name}</h2>
            <span className="turnos-badge">{stop.picked_up_at ? `Retirado ${timeLabel(stop.picked_up_at)}` : isNext ? 'Siguiente' : 'Pendiente'}</span>
            <p className="transporte-text"><small>{stop.center.address}, {stop.center.city} · {samples(stop.samples.length)}</small></p>
            {isNext && <Link className="turnos-action transporte-primary" to={`/transporte/centro/${stop.id}`}>Ir al centro</Link>}
          </div>
        </li>
      })}</ol>
      <div className="turnos-card transporte-map-card">
        <h2>Recorrido</h2>
        <p className="transporte-text"><small>Laboratorio Central → centros en orden → Laboratorio Central</small></p>
        <RecorridoMap lab={route.central_lab} stops={route.stops} />
      </div>
    </div>
    <div className="turnos-links transporte-footer">
      <Link className="turnos-action-secondary" to="/transporte">Volver al inicio</Link>
      <Link className="turnos-action-secondary" to="/transporte/a-bordo">Muestras a bordo</Link>
    </div>
  </>
}

// Ventana modal de confirmación (P4 y P8). Escape o Cancelar la cierran mientras no se esté enviando;
// el foco queda adentro (Tab da la vuelta) y al cerrar vuelve al botón que la abrió.
function Confirmacion({ title, children, confirmLabel, sending, error, onConfirm, onCancel }) {
  const dialog = useRef(null)
  const confirmButton = useRef(null)
  useEffect(() => {
    const opener = document.activeElement
    return () => opener?.focus?.()
  }, [])
  // Al abrir y después de un envío fallido: el botón deshabilitado pierde el foco.
  useEffect(() => { if (!sending) confirmButton.current?.focus() }, [sending])
  useEffect(() => {
    function onKeyDown(event) {
      if (event.key === 'Escape' && !sending) onCancel()
      if (event.key !== 'Tab') return
      const buttons = [...dialog.current.querySelectorAll('button:not(:disabled)')]
      if (!buttons.length) return
      const [first, last] = [buttons[0], buttons.at(-1)]
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus() }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus() }
    }
    document.addEventListener('keydown', onKeyDown)
    return () => document.removeEventListener('keydown', onKeyDown)
  }, [sending, onCancel])
  return <div className="transporte-modal-backdrop">
    <div ref={dialog} role="dialog" aria-modal="true" aria-label={title} className="transporte-modal">
      <h2>{title}</h2>
      {children}
      {error && <p role="alert" className="turnos-error">{error}</p>}
      <div className="transporte-modal-actions">
        <button type="button" onClick={onCancel} disabled={sending}>Cancelar</button>
        <button type="button" ref={confirmButton} className="turnos-action" onClick={onConfirm} disabled={sending}>{sending ? 'Registrando...' : confirmLabel}</button>
      </div>
    </div>
  </div>
}

// Comprobante de P5 y P9: sello de hora, lugar, cantidad de muestras y custodia transferida.
function Comprobante({ title, stamp, place, codes, custody, message, children }) {
  return <article className="turnos-card transporte-receipt" aria-label={title}>
    <PackageCheck className="transporte-receipt-icon" aria-hidden="true" />
    <h2>{title}</h2>
    <p role="status" className="transporte-receipt-message">{message}</p>
    <dl>
      <dt>Hora</dt><dd className="transporte-stamp">{stamp}</dd>
      <dt>Lugar</dt><dd>{place}</dd>
      <dt>Muestras</dt><dd>{codes.length}</dd>
      <dt>Custodia</dt><dd>{custody}</dd>
    </dl>
    <ul className="transporte-codes">{codes.map((code) => <li key={code}>{code}</li>)}</ul>
    {children}
  </article>
}

function SamplesTable({ caption, rows }) {
  return <div className="transporte-table-wrap"><table className="transporte-table">
    <caption>{caption}</caption>
    <thead><tr><th scope="col">Código</th><th scope="col">Volumen</th><th scope="col">Extracción</th></tr></thead>
    <tbody>{rows.map((sample) => <tr key={sample.code}>
      <th scope="row">{sample.code}</th><td>{volumeLabel(sample.volume_ml)}</td><td>{takenLabel(sample.taken_at)}</td>
    </tr>)}</tbody>
  </table></div>
}

// Una instancia por parada: al pasar al siguiente centro no queda el comprobante del anterior.
function Centro(props) {
  const { stopId } = useParams()
  return <Parada key={stopId} stopId={stopId} {...props} />
}

// P3 centro, P4 confirmar retiro y P5 comprobante.
function Parada({ stopId, route, onChanged }) {
  const stop = route.stops.find((item) => String(item.id) === stopId)
  const [confirming, setConfirming] = useState(false)
  const [sending, setSending] = useState(false)
  const [error, setError] = useState('')
  const [receipt, setReceipt] = useState(null)
  if (!stop) return <Navigate to="/transporte/orden" replace />

  async function confirm() {
    setSending(true); setError('')
    try {
      setReceipt(await pickUp(route.id, stop.id))
      setConfirming(false)
      onChanged()
    } catch (failure) {
      setError(errorMessage(failure))
    } finally {
      setSending(false)
    }
  }
  function cancel() { setConfirming(false); setError('') }

  const next = nextStop(route)
  // Para el comprobante, el siguiente sale de la secuencia: la orden recargada puede no haber llegado todavía.
  const after = route.stops.find((item) => item.sequence === stop.sequence + 1)
  if (receipt) return <>
    <Heading title={stop.center.name}><p>Parada {stop.sequence} de {route.stops.length} · {stop.center.address}, {stop.center.city}</p></Heading>
    <Comprobante title="Retiro registrado" stamp={timeLabel(receipt.picked_up_at)} place={receipt.center.name} codes={receipt.sample_codes}
      custody="Transferida al transportista" message={`Retiro registrado a las ${timeLabel(receipt.picked_up_at)}: retiraste ${samples(receipt.sample_codes.length)} de este centro.`}>
      {after ? <Link className="turnos-action transporte-primary" to={`/transporte/centro/${after.id}`}>Siguiente centro</Link>
        : <Link className="turnos-action transporte-primary" to="/transporte/a-bordo">Registrar llegada</Link>}
      <div className="turnos-links"><Link className="turnos-action-secondary" to="/transporte/a-bordo">Muestras a bordo</Link></div>
    </Comprobante>
  </>
  return <>
    <Heading title={stop.center.name}><p>Parada {stop.sequence} de {route.stops.length} · {stop.center.address}, {stop.center.city}</p></Heading>
    <div className="turnos-card transporte-center">
      <div className="transporte-center-head">
        <MapPin aria-hidden="true" />
        <div><span className="turnos-badge">{stop.picked_up_at ? `Retirado ${timeLabel(stop.picked_up_at)}` : stop.id === route.next_stop_id ? 'Siguiente' : 'Pendiente'}</span>
          <p className="transporte-text"><strong>{stop.center.name}</strong><small>{stop.center.address}, {stop.center.city}</small></p></div>
        <p className="transporte-total"><strong>{stop.samples.length}</strong>{stop.samples.length === 1 ? 'muestra' : 'muestras'}</p>
      </div>
      {stop.samples.length ? <SamplesTable caption={stop.picked_up_at ? 'Muestras retiradas' : 'Muestras para retirar'} rows={stop.samples} />
        : <p className="turnos-empty">El centro no tiene muestras listas en este momento.</p>}
      {stop.picked_up_at ? <div className="turnos-links"><Link className="turnos-action-secondary" to="/transporte/orden">Volver a la orden</Link></div>
        : stop.id !== route.next_stop_id ? <><p className="turnos-note">El orden es fijo: primero retirá la parada {next?.sequence}.</p>
          <div className="turnos-links"><Link className="turnos-action-secondary" to="/transporte/orden">Volver a la orden</Link></div></>
          : <div className="transporte-actions">
            <button type="button" className="turnos-action transporte-primary" onClick={() => setConfirming(true)}>Registrar retiro</button>
            <Link className="turnos-action-secondary" to="/transporte/orden">Volver a la orden</Link>
          </div>}
    </div>
    {confirming && <Confirmacion title="Confirmar retiro" confirmLabel="Confirmar retiro" sending={sending} error={error} onConfirm={confirm} onCancel={cancel}>
      <p>¿Confirmás el retiro de {samples(stop.samples.length)} de este centro?</p>
      <p className="transporte-text"><small>Al confirmar, las muestras quedan bajo tu custodia hasta el Laboratorio Central.</small></p>
    </Confirmacion>}
  </>
}

// P6 a bordo, P7 fin de recorrido, P8 confirmar llegada y P9 llegada registrada.
function ABordo({ route, onChanged }) {
  const [confirming, setConfirming] = useState(false)
  const [sending, setSending] = useState(false)
  const [error, setError] = useState('')
  const [receipt, setReceipt] = useState(null)
  const picked = pickedStops(route)
  const missing = route.stops.length - picked.length

  async function confirm() {
    setSending(true); setError('')
    try {
      setReceipt(await registerArrival(route.id))
      setConfirming(false)
      onChanged()
    } catch (failure) {
      setError(errorMessage(failure))
    } finally {
      setSending(false)
    }
  }
  function cancel() { setConfirming(false); setError('') }

  if (receipt) return <>
    <Heading title="Llegada registrada"><p>Laboratorio Central, {timeLabel(receipt.arrived_at)}.</p></Heading>
    <Comprobante title="Llegada confirmada" stamp={timeLabel(receipt.arrived_at)} place={route.central_lab.address} codes={receipt.received_codes}
      custody="Transferida al Laboratorio Central" message={`${receipt.received_codes.length === 1 ? 'Se recibió' : 'Se recibieron'} ${samples(receipt.received_codes.length)} en el Laboratorio Central.`}>
      <Link className="turnos-action transporte-primary" to="/transporte">Volver al inicio</Link>
    </Comprobante>
  </>
  const finished = route.status === 'pending' && missing === 0
  return <>
    <Heading title={finished ? 'Fin del recorrido' : 'Muestras a bordo'}><p>{route.province} · {picked.length} de {route.stops.length} centros retirados.</p></Heading>
    {route.status === 'arrived' ? <p className="turnos-note">La llegada ya fue registrada a las {timeLabel(route.arrived_at)}.</p>
      : route.on_board.length ? <div className="turnos-card"><div className="transporte-table-wrap"><table className="transporte-table">
        <caption>Muestras bajo tu custodia</caption>
        <thead><tr><th scope="col">Código</th><th scope="col">Volumen</th><th scope="col">Extracción</th></tr></thead>
        {picked.filter((stop) => stop.samples.length).map((stop) => <tbody key={stop.id}>
          <tr className="transporte-group"><th scope="rowgroup" colSpan="3">{stop.sequence}. {stop.center.name} · retirado {timeLabel(stop.picked_up_at)}</th></tr>
          {stop.samples.map((sample) => <tr key={sample.code}><th scope="row">{sample.code}</th><td>{volumeLabel(sample.volume_ml)}</td><td>{takenLabel(sample.taken_at)}</td></tr>)}
        </tbody>)}
      </table></div></div>
        : <p className="turnos-empty">Todavía no retiraste muestras.</p>}
    {route.status === 'pending' && (missing ? <div className="turnos-card transporte-next-card">
      <p className="turnos-note">Faltan retirar {count(missing, 'centro', 'centros')} antes de registrar la llegada.</p>
      <Link className="turnos-action transporte-primary" to={`/transporte/centro/${route.next_stop_id}`}>Ir al siguiente centro</Link></div>
      : <section className="turnos-card transporte-next-card" aria-labelledby="transporte-fin">
        <h2 id="transporte-fin">Balance de la jornada</h2>
        <ul className="transporte-kpis transporte-balance">
          <li><strong>{picked.length} de {route.stops.length}</strong>Centros visitados</li>
          <li className="transporte-kpi-accent"><strong>{route.on_board.length}</strong>Muestras a entregar</li>
          <li><strong>Laboratorio Central</strong>{route.central_lab.address}</li>
        </ul>
        <button type="button" className="turnos-action transporte-primary" onClick={() => setConfirming(true)}>Registrar llegada</button>
      </section>)}
    <div className="turnos-links transporte-footer"><Link className="turnos-action-secondary" to="/transporte">Volver al inicio</Link></div>
    {confirming && <Confirmacion title="Confirmar llegada" confirmLabel="Confirmar llegada" sending={sending} error={error} onConfirm={confirm} onCancel={cancel}>
      <p>¿Confirmás la llegada al Laboratorio Central con {samples(route.on_board.length)}?</p>
      <p className="transporte-text"><small>Al confirmar, la custodia pasa al Laboratorio Central.</small></p>
    </Confirmacion>}
  </>
}
