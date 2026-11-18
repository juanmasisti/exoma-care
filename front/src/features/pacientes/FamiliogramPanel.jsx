import { useEffect, useRef, useState } from 'react'
import { errorMessage } from '../../services/api.js'
import { generateFamiliogram, getFamiliograms, getFamiliogramFile, getPatientVersion } from './familyApi.js'

export default function FamiliogramPanel({ patientId, familyVersion, editing, active, members = [] }) {
  const incomplete = members.filter(member => !member.first_name?.trim() || !member.last_name?.trim() || !member.provider_relationship)
  const alive = useRef(true)
  useEffect(() => { alive.current = true; return () => { alive.current = false } }, [])
  const [documents, setDocuments] = useState([])
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [preview, setPreview] = useState('')
  useEffect(() => {
    if (!active) return
    let cancelled = false
    getFamiliograms(patientId).then(data => { if (!cancelled) setDocuments(data) }).catch(e => { if (!cancelled) setError(errorMessage(e)) })
    return () => { cancelled = true }
  }, [patientId, familyVersion, active])
  useEffect(() => () => { if (preview) URL.revokeObjectURL(preview) }, [preview])
  async function generate() {
    setBusy(true); setError('')
    try {
      const patientVersion = await getPatientVersion(patientId)
      await generateFamiliogram(patientId, { patient_version: patientVersion, family_version: familyVersion })
      const updated = await getFamiliograms(patientId)
      if (alive.current) setDocuments(updated)
    } catch (e) { if (alive.current) setError(errorMessage(e)) }
    finally { if (alive.current) setBusy(false) }
  }
  async function file(document, format) {
    setError('')
    try {
      const blob = await getFamiliogramFile(patientId, document.id, format)
      if (!alive.current) return
      const url = URL.createObjectURL(blob)
      if (format === 'svg') setPreview(url)
      else {
        const anchor = window.document.createElement('a')
        anchor.href = url; anchor.download = `familiograma-${patientId}-${document.id}.pdf`; anchor.click()
        setTimeout(() => URL.revokeObjectURL(url), 1000)
      }
    } catch (e) { if (alive.current) setError(errorMessage(e)) }
  }
  return <section className="family-history" aria-label="Familiograma">
    <h3>Familiograma y PDF</h3>
    <p className="patient-help">Se envían al generador los nombres y antecedentes de la versión guardada. El dibujo muestra los diagnósticos confirmados que registraste. El paciente se representa con sexo no identificado, porque la ficha no registra ese dato.</p>
    <button type="button" disabled={busy || editing || incomplete.length > 0} onClick={generate}>{busy ? 'Generando familiograma...' : 'Generar familiograma y PDF'}</button>
    {incomplete.length > 0 && <p role="status">Antes de generar, completá nombres, apellidos y parentesco del familiograma de: {incomplete.map(member => member.full_name).join(", ")}.</p>}
    {editing && <p>Guardá o cancelá la edición familiar antes de generar.</p>}
    {error && <p role="alert" className="patient-error">{error}</p>}
    {documents.map(document => <article key={document.id} className="family-member">
      <p>Documento {document.id} · {new Date(document.created_at).toLocaleString('es-AR')} · Ficha {document.patient_version} / Familia {document.family_version}</p>
      {(document.stale || document.family_version !== familyVersion) && <p role="status">Desactualizado: corresponde a una versión anterior. Generá uno nuevo.</p>}
      {document.warnings.map((warning, index) => <p key={index}>{warning.mensaje}</p>)}
      <div className="family-actions"><button type="button" onClick={() => file(document, 'svg')}>Ver familiograma {document.id}</button><button type="button" onClick={() => file(document, 'pdf')}>Descargar PDF {document.id}</button></div>
    </article>)}
    {preview && <div><button type="button" onClick={() => setPreview('')}>Cerrar vista</button><img src={preview} alt="Familiograma de la versión seleccionada" style={{ width: '100%', maxHeight: 800, objectFit: 'contain' }} /></div>}
  </section>
}
