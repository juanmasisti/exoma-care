import { useCallback, useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { Boxes } from 'lucide-react'
import ClinicalLayout from '../../../components/layout/ClinicalLayout.jsx'
import { errorMessage } from '../../../services/api.js'
import EnvioLote from './EnvioLote.jsx'
import { Badges, Dates } from './ResumenLote.jsx'
import { getSampleSet } from './api.js'
import '../turnos/turnos.css'
import './lotes.css'

// Contrato con T06: <EnvioLote session sampleSetId onChange />; onChange recarga el lote cuando el envío lo cambia.
export default function DetalleLote({ session }) {
  const { sampleSetId } = useParams()
  // La respuesta guarda de qué lote es: al pasar a otro lote no se ve el anterior ni su "no existe".
  const [result, setResult] = useState(null)
  const [retry, setRetry] = useState(0)
  const current = result?.id === sampleSetId ? result : null
  const reload = useCallback(() => setRetry((n) => n + 1), [])

  useEffect(() => {
    let active = true
    getSampleSet(sampleSetId)
      .then((sampleSet) => { if (active) setResult({ id: sampleSetId, sampleSet, missing: false, error: '' }) })
      .catch((failure) => {
        if (!active) return
        // Si falla una recarga se conserva el lote ya cargado: el panel del envío no se desmonta.
        setResult((previous) => ({ id: sampleSetId, sampleSet: previous?.id === sampleSetId ? previous.sampleSet : null,
          missing: failure.response?.status === 404, error: errorMessage(failure) }))
      })
    return () => { active = false }
  }, [sampleSetId, retry])

  const sampleSet = current?.sampleSet
  const alert = current?.error && !current.missing && <div role="alert" className="turnos-error"><p>{current.error}</p>
    <button type="button" onClick={reload}>Reintentar</button></div>

  return <ClinicalLayout session={session} pageLabel={`Lote ${sampleSetId}`}><section className="turnos-page turnos-patient lotes-detalle">
    <header className="turnos-heading"><span>SAMPLE SET</span><h1><Boxes aria-hidden="true" />Lote {sampleSetId}</h1></header>
    {current?.missing ? <div className="turnos-card"><p className="turnos-empty">Este lote no existe.</p>
      <div className="turnos-links"><Link className="turnos-action-secondary" to="/administrativo/lotes">Volver a lotes</Link></div></div>
      : !sampleSet ? alert || <p role="status" className="turnos-loading">Cargando lote...</p>
        : <>
          {alert}
          <article className="turnos-card turnos-appointment" aria-labelledby="lote-datos">
            <h2 id="lote-datos">Datos del lote</h2>
            <Badges sampleSet={sampleSet} />
            <Dates sampleSet={sampleSet} count={sampleSet.samples.length} />
          </article>
          <section className="turnos-card" aria-labelledby="lote-muestras">
            <h2 id="lote-muestras">Muestras</h2>
            {sampleSet.samples.length === 0 ? <p className="turnos-empty">El lote todavía no tiene muestras.</p>
              : <ol className="lotes-samples">{sampleSet.samples.map((sample) => <li key={sample.slot}>
                <span>Lugar {sample.slot}</span><strong>{sample.study_code}</strong>
              </li>)}</ol>}
          </section>
          <EnvioLote session={session} sampleSetId={sampleSetId} onChange={reload} />
        </>}
  </section></ClinicalLayout>
}
