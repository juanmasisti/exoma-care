import { useEffect, useState } from 'react'
import { Link, Navigate, Route, Routes, useParams } from 'react-router-dom'
import { Truck } from 'lucide-react'
import ClinicalLayout from '../../../components/layout/ClinicalLayout.jsx'
import { errorMessage } from '../../../services/api.js'
import { listProvinces } from '../turnos/api.js'
import { dateLabel, timeLabel } from '../turnos/fecha.js'
import { getMyRoute, pickUp, registerArrival, today } from './api.js'
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

  return <ClinicalLayout session={session}><section className="turnos-page turnos-patient">
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

// P1: provincia (PROVISORIO hasta el rol transportista con provincia), resumen y siguiente centro.
function Inicio({ date, provinceId, onProvince, route, error }) {
  const [provinces, setProvinces] = useState(null)
  const [provincesError, setProvincesError] = useState('')
  useEffect(() => {
    let active = true
    listProvinces().then((data) => { if (active) setProvinces(data) })
      .catch((failure) => { if (active) setProvincesError(errorMessage(failure)) })
    return () => { active = false }
  }, [])

  const next = route && nextStop(route)
  return <>
    <Heading title="Tu recorrido de hoy"><p>{dateLabel(date)}. Retirá en el orden fijo y llevá las muestras al Laboratorio Central.</p></Heading>
    <div className="turnos-card transporte-block">
      <label htmlFor="transporte-province">Provincia (PROVISORIO: después sale de tu usuario)</label>
      {provincesError ? <p role="alert" className="turnos-error">{provincesError}</p>
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
                <li><strong>{route.on_board.length}</strong>Muestras a bordo</li>
              </ul>
              <div className="turnos-card turnos-appointment">
                {route.status === 'arrived' ? <><h2>Recorrido terminado</h2>
                  <p className="transporte-text">Llegada al Laboratorio Central registrada a las {timeLabel(route.arrived_at)}.</p></>
                  : next ? <><h2>Siguiente centro</h2><span className="turnos-badge">Parada {next.sequence} de {route.stops.length}</span>
                    <p className="transporte-text"><strong>{next.center.name}</strong><small>{next.center.address}, {next.center.city}</small></p></>
                    : <><h2>Retiraste todos los centros</h2><p className="transporte-text">Registrá la llegada al Laboratorio Central.</p></>}
                <div className="turnos-links">
                  {route.status === 'pending' && (next
                    ? <Link className="turnos-action" to={`/transporte/centro/${next.id}`}>Ir al centro</Link>
                    : <Link className="turnos-action" to="/transporte/a-bordo">Registrar llegada</Link>)}
                  <Link className="turnos-action-secondary" to="/transporte/orden">Ver orden completa</Link>
                  <Link className="turnos-action-secondary" to="/transporte/a-bordo">Muestras a bordo</Link>
                </div>
              </div>
            </>}
  </>
}

// P2: paradas en la secuencia de la API de recorridos; solo la siguiente se puede abrir para retirar.
function Orden({ route }) {
  return <>
    <Heading title={`Orden del día · ${route.province}`}><p>El orden es fijo: no se puede cambiar ni saltear un centro.</p></Heading>
    <ol className="turnos-list">{route.stops.map((stop) => {
      const isNext = stop.id === route.next_stop_id
      return <li key={stop.id} className={`turnos-card turnos-appointment${isNext ? ' transporte-next' : ''}`}>
        <h2>{stop.sequence}. {stop.center.name}</h2>
        <span className={stop.picked_up_at ? 'turnos-badge' : isNext ? 'turnos-badge transporte-badge-next' : 'turnos-badge transporte-badge-pending'}>
          {stop.picked_up_at ? `Retirado ${timeLabel(stop.picked_up_at)}` : isNext ? 'Siguiente' : 'Pendiente'}</span>
        <p className="transporte-text"><small>{stop.center.address}, {stop.center.city} · {samples(stop.sample_codes.length)}</small></p>
        {isNext && <div className="turnos-links"><Link className="turnos-action" to={`/transporte/centro/${stop.id}`}>Ir al centro</Link></div>}
      </li>
    })}</ol>
    <div className="turnos-links"><Link className="turnos-action-secondary" to="/transporte">Volver al inicio</Link></div>
  </>
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

  const next = nextStop(route)
  // Para el comprobante, el siguiente sale de la secuencia: la orden recargada puede no haber llegado todavía.
  const after = route.stops.find((item) => item.sequence === stop.sequence + 1)
  const codes = receipt ? receipt.sample_codes : stop.sample_codes
  return <>
    <Heading title={stop.center.name}><p>Parada {stop.sequence} de {route.stops.length} · {stop.center.address}, {stop.center.city}</p></Heading>
    <div className="turnos-card turnos-appointment">
      {receipt ? <p role="status" className="turnos-note">Retiro registrado a las {timeLabel(receipt.picked_up_at)}: retiraste {samples(receipt.sample_codes.length)} de este centro.</p>
        : stop.picked_up_at && <span className="turnos-badge">Retirado {timeLabel(stop.picked_up_at)}</span>}
      <h2>{stop.picked_up_at || receipt ? 'Muestras retiradas' : 'Muestras para retirar'}</h2>
      {codes.length ? <ul className="transporte-codes">{codes.map((code) => <li key={code}>{code}</li>)}</ul>
        : <p className="turnos-empty">El centro no tiene muestras listas en este momento.</p>}
      {error && <p role="alert" className="turnos-error">{error}</p>}
      {receipt ? <div className="turnos-links">
        {after ? <Link className="turnos-action" to={`/transporte/centro/${after.id}`}>Siguiente centro</Link>
          : <Link className="turnos-action" to="/transporte/a-bordo">Registrar llegada</Link>}
        <Link className="turnos-action-secondary" to="/transporte/a-bordo">Muestras a bordo</Link>
      </div>
        : stop.picked_up_at ? <div className="turnos-links"><Link className="turnos-action-secondary" to="/transporte/orden">Volver a la orden</Link></div>
          : stop.id !== route.next_stop_id ? <><p className="turnos-note">El orden es fijo: primero retirá la parada {next?.sequence}.</p>
            <div className="turnos-links"><Link className="turnos-action-secondary" to="/transporte/orden">Volver a la orden</Link></div></>
            : confirming ? <div className="turnos-confirm transporte-confirm" role="group" aria-label="Confirmar retiro">
              <p>¿Confirmás el retiro de {samples(codes.length)} de este centro?</p>
              <button type="button" className="turnos-action" onClick={confirm} disabled={sending}>{sending ? 'Registrando...' : 'Confirmar retiro'}</button>
              <button type="button" onClick={() => setConfirming(false)} disabled={sending}>Cancelar</button>
            </div>
              : <div className="turnos-links"><button type="button" className="turnos-action" onClick={() => setConfirming(true)}>Registrar retiro</button>
                <Link className="turnos-action-secondary" to="/transporte/orden">Volver a la orden</Link></div>}
    </div>
  </>
}

// P6 a bordo, P7 fin de recorrido, P8 confirmar llegada y P9 llegada registrada.
function ABordo({ route, onChanged }) {
  const [confirming, setConfirming] = useState(false)
  const [sending, setSending] = useState(false)
  const [error, setError] = useState('')
  const [receipt, setReceipt] = useState(null)
  const missing = route.stops.length - pickedStops(route).length

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

  if (receipt) return <>
    <Heading title="Llegada registrada"><p>Laboratorio Central, {timeLabel(receipt.arrived_at)}.</p></Heading>
    <div className="turnos-card turnos-appointment">
      <p role="status" className="turnos-note">Se recibieron {samples(receipt.received_codes.length)} en el Laboratorio Central.</p>
      <ul className="transporte-codes">{receipt.received_codes.map((code) => <li key={code}>{code}</li>)}</ul>
      <div className="turnos-links"><Link className="turnos-action" to="/transporte">Volver al inicio</Link></div>
    </div>
  </>
  return <>
    <Heading title="Muestras a bordo"><p>{route.province} · {pickedStops(route).length} de {route.stops.length} centros retirados.</p></Heading>
    <div className="turnos-card turnos-appointment">
      {route.status === 'arrived' ? <p className="turnos-note">La llegada ya fue registrada a las {timeLabel(route.arrived_at)}.</p>
        : route.on_board.length ? <ul className="transporte-codes">{route.on_board.map((code) => <li key={code}>{code}</li>)}</ul>
          : <p className="turnos-empty">Todavía no retiraste muestras.</p>}
      {error && <p role="alert" className="turnos-error">{error}</p>}
      {route.status === 'pending' && (missing ? <>
        <p className="turnos-note">Faltan retirar {count(missing, 'centro', 'centros')} antes de registrar la llegada.</p>
        <div className="turnos-links"><Link className="turnos-action" to={`/transporte/centro/${route.next_stop_id}`}>Ir al siguiente centro</Link></div></>
        : confirming ? <div className="turnos-confirm transporte-confirm" role="group" aria-label="Confirmar llegada">
          <p>¿Confirmás la llegada al Laboratorio Central con {samples(route.on_board.length)}?</p>
          <button type="button" className="turnos-action" onClick={confirm} disabled={sending}>{sending ? 'Registrando...' : 'Confirmar llegada'}</button>
          <button type="button" onClick={() => setConfirming(false)} disabled={sending}>Cancelar</button>
        </div>
          : <><h2>Fin de recorrido</h2><div className="turnos-links">
            <button type="button" className="turnos-action" onClick={() => setConfirming(true)}>Registrar llegada</button></div></>)}
      <div className="turnos-links"><Link className="turnos-action-secondary" to="/transporte">Volver al inicio</Link></div>
    </div>
  </>
}
