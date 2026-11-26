import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { Boxes } from 'lucide-react'
import ClinicalLayout from '../../../components/layout/ClinicalLayout.jsx'
import { errorMessage } from '../../../services/api.js'
import { listSampleSets } from './api.js'
import { SAMPLE_SET_STATUSES, statusLabel } from './estados.js'
import { Badges, Dates } from './ResumenLote.jsx'
import '../turnos/turnos.css'
import './lotes.css'

export default function ListaLotes({ session }) {
  // El estado va en la URL: al volver del detalle se ve la misma pestaña.
  const [searchParams, setSearchParams] = useSearchParams()
  const requested = searchParams.get('estado')
  const status = SAMPLE_SET_STATUSES.some(([value]) => value === requested) ? requested : 'assembling'
  // La respuesta guarda de qué estado es: al cambiar de pestaña se ve "Cargando" y no la lista anterior.
  const [result, setResult] = useState(null)
  const [retry, setRetry] = useState(0)
  const current = result?.status === status ? result : null

  useEffect(() => {
    let active = true
    listSampleSets(status)
      .then((sampleSets) => { if (active) setResult({ status, sampleSets, error: '' }) })
      .catch((failure) => { if (active) setResult({ status, sampleSets: null, error: errorMessage(failure) }) })
    return () => { active = false }
  }, [status, retry])

  return <ClinicalLayout session={session}><section className="turnos-page turnos-patient">
    <header className="turnos-heading"><span>SAMPLE SETS</span><h1><Boxes aria-hidden="true" />Lotes</h1>
      <p>Las muestras recibidas se agrupan solas en lotes de 10. Un Pompe urgente cierra el lote antes.</p></header>
    <div className="lotes-tabs" role="group" aria-label="Estado de los lotes">
      {SAMPLE_SET_STATUSES.map(([value, label]) => <button key={value} type="button" aria-pressed={value === status}
        onClick={() => setSearchParams({ estado: value })}>{label}</button>)}
    </div>
    {current?.error ? <div role="alert" className="turnos-error"><p>{current.error}</p>
      <button type="button" onClick={() => { setResult(null); setRetry((n) => n + 1) }}>Reintentar</button></div>
      : !current ? <p role="status" className="turnos-loading">Cargando lotes...</p>
        : current.sampleSets.length === 0 ? <div className="turnos-card"><p className="turnos-empty">No hay lotes en «{statusLabel(status)}».</p></div>
          : <ul className="turnos-list">{current.sampleSets.map((sampleSet) => <li key={sampleSet.id} className="turnos-card turnos-appointment">
            <h2>Lote {sampleSet.id}</h2>
            <Badges sampleSet={sampleSet} />
            <Dates sampleSet={sampleSet} count={sampleSet.sample_count} />
            <div className="turnos-links"><Link className="turnos-action" to={`/administrativo/lotes/${sampleSet.id}`}>Ver lote</Link></div>
          </li>)}</ul>}
  </section></ClinicalLayout>
}
