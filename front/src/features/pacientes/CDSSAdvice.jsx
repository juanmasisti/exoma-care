import { useEffect, useRef, useState } from 'react'
import { getCDSSAdvice } from '../patologias/clinicalIntegrationsApi.js'
import { errorMessage } from '../../services/api.js'

export default function CDSSAdvice({ symptoms }) {
  const key = symptoms.map((s) => s.id).sort((a, b) => a - b).join(',')
  return <Advice key={key} symptoms={symptoms} />
}
function Advice({ symptoms }) {
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const controller = useRef(null)
  useEffect(() => () => controller.current?.abort(), [])
  async function consult() {
    controller.current?.abort()
    const request = new AbortController()
    controller.current = request
    setBusy(true); setError(''); setResult(null)
    try {
      const data = await getCDSSAdvice(symptoms.map((s) => s.id), request.signal)
      if (!request.signal.aborted) setResult(data)
    } catch (failure) {
      if (!request.signal.aborted) setError(errorMessage(failure))
    } finally { if (!request.signal.aborted) setBusy(false) }
  }
  return <section className="patient-pathology-criteria" aria-label="Orientación CDSS">
    <h3>Orientación CDSS</h3>
    <p className="patient-help">Consulta opcional. No establece un diagnóstico ni reemplaza el criterio local de un cardinal o dos secundarios. Las sugerencias no se guardan como sospechas.</p>
    <button type="button" className="patient-secondary" onClick={consult} disabled={busy || !symptoms.some((s) => s.code_system === 'SNOMED')}>{busy ? 'Consultando CDSS...' : 'Consultar orientación CDSS'}</button>
    <p className="patient-help">Sólo se envían códigos SNOMED; se excluyen conceptos DEMO.</p>
    {error && <p role="alert" className="patient-error">{error}</p>}
    {result && <div role="status">
      <p><strong>{result.result.compatible ? 'Sugerencias orientativas' : 'CDSS no encontró compatibilidad'}</strong></p>
      {result.result.mensaje && <p>{result.result.mensaje}</p>}
      <p>Estrategia del grupo: {result.result.estrategia}</p>
      <ul>{result.result.patologias.map((p) => <li key={p.codigo}>{p.nombre} ({p.codigo})</li>)}</ul>
      {result.result.ranking.length > 0 && <><h4>Orden de coincidencias</h4><ol>{result.result.ranking.map((p) => <li key={p.codigo}>{p.codigo}: puntaje {p.puntaje}; {p.cardinales_coincidentes} cardinales, {p.sintomas_coincidentes} síntomas coincidentes.</li>)}</ol></>}
      {result.excluded_symptom_ids.length > 0 && <p>Se excluyeron {result.excluded_symptom_ids.length} conceptos sin código SNOMED válido.</p>}
      <p>Revisá las sugerencias y elegí las sospechas manualmente. Un resultado sin compatibilidad no impide la validación local.</p>
    </div>}
  </section>
}
