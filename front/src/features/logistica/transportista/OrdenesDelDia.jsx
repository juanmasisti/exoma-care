import { useEffect, useState } from 'react'
import { Route as RouteIcon } from 'lucide-react'
import ClinicalLayout from '../../../components/layout/ClinicalLayout.jsx'
import { errorMessage } from '../../../services/api.js'
import { dateLabel } from '../turnos/fecha.js'
import { ROUTE_STATUS, generateDailyRoutes, listDailyRoutes, today } from './api.js'
import '../turnos/turnos.css'
import './transportista.css'

export default function OrdenesDelDia({ session }) {
  const [date, setDate] = useState(today())
  const [routes, setRoutes] = useState(null)
  const [error, setError] = useState('')
  const [retry, setRetry] = useState(0)
  const [generating, setGenerating] = useState(false)
  const [result, setResult] = useState(null)  // { ok, text } del último "Generar"

  useEffect(() => {
    if (!date) return undefined
    let active = true
    listDailyRoutes(date).then((data) => { if (active) setRoutes(data) })
      .catch((failure) => { if (active) setError(errorMessage(failure)) })
    return () => { active = false }
  }, [date, retry])

  function changeDate(value) {
    setDate(value); setRoutes(null); setError(''); setResult(null)
  }

  async function generate() {
    setGenerating(true); setResult(null)
    try {
      const { created, routes: generated } = await generateDailyRoutes(date)
      setRoutes(generated); setError('')
      setResult({ ok: true, text: created ? 'Se generaron las órdenes que faltaban.'
        : generated.length ? 'Las órdenes de este día ya estaban generadas.'
          : 'No hay muestras listas para retirar: no se generó ninguna orden.' })
    } catch (failure) {
      setResult({ ok: false, text: errorMessage(failure) })
    } finally {
      setGenerating(false)
    }
  }

  return <ClinicalLayout session={session}><section className="turnos-page turnos-patient">
    <header className="turnos-heading"><span>GESTIÓN ADMINISTRATIVA</span><h1><RouteIcon aria-hidden="true" />Órdenes del día</h1>
      <p>Una orden por provincia con los centros que tienen muestras listas, en el orden que calcula el módulo de recorridos.</p></header>
    <div className="turnos-card transporte-toolbar">
      <div><label htmlFor="transporte-date">Fecha</label>
        <input id="transporte-date" type="date" value={date} onChange={(event) => changeDate(event.target.value)} disabled={generating} /></div>
      <button type="button" className="turnos-action" onClick={generate} disabled={generating || !date}>
        {generating ? 'Generando...' : 'Generar órdenes'}</button>
    </div>
    {result && <p role={result.ok ? 'status' : 'alert'} className={result.ok ? 'turnos-note transporte-result' : 'turnos-error transporte-result'}>{result.text}</p>}
    {!date ? <div className="turnos-card"><p className="turnos-empty">Elegí una fecha.</p></div>
      : error ? <div role="alert" className="turnos-error"><p>{error}</p><button type="button" onClick={() => { setError(''); setRetry((n) => n + 1) }}>Reintentar</button></div>
      : !routes ? <p role="status" className="turnos-loading">Cargando órdenes...</p>
        : routes.length === 0 ? <div className="turnos-card"><p className="turnos-empty">No hay órdenes para el {dateLabel(date)}.</p></div>
          : <ul className="turnos-list">{routes.map((route) => <li key={route.id} className="turnos-card turnos-appointment">
            <h2>{route.province}</h2>
            <span className="turnos-badge">{ROUTE_STATUS[route.status] ?? route.status}</span>
            <Progress done={route.picked_up} total={route.stops} />
          </li>)}</ul>}
  </section></ClinicalLayout>
}

function Progress({ done, total }) {
  return <div className="transporte-progress">
    <p>Centros retirados: <strong>{done} de {total}</strong></p>
    <progress value={done} max={total} aria-label={`Centros retirados: ${done} de ${total}`} />
  </div>
}
