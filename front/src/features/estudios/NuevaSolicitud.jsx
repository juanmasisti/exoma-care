import { useEffect, useMemo, useState } from 'react'
import { AlertCircle, ArrowLeft, Dna, Plus, Search, X } from 'lucide-react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import ClinicalLayout from '../../components/layout/ClinicalLayout.jsx'
import { errorMessage } from '../../services/api.js'
import { listPatients } from '../pacientes/api.js'
import { createStudyRequest, getPathologyCatalog, getStudyRequest, requestReanalysis, searchGenes } from './api.js'
import { estimateTotalCents, money, REANALYSIS_DISCOUNT_PERCENT } from './format.js'
import './estudios.css'

// También arma el reanálisis (EC-14): ruta /estudios/:studyId/reanalisis, mismo paciente y exoma.
export default function NuevaSolicitud({ session }) {
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const { studyId } = useParams()
  const reanalysis = Boolean(studyId)
  const [origin, setOrigin] = useState(null)
  const [originError, setOriginError] = useState('')
  const [geneNotice, setGeneNotice] = useState('')
  const [catalog, setCatalog] = useState(null)
  const [catalogError, setCatalogError] = useState('')
  const [patientQuery, setPatientQuery] = useState('')
  const [patientResults, setPatientResults] = useState([])
  const [patient, setPatient] = useState(null)
  const [codes, setCodes] = useState([])
  const [extraGenes, setExtraGenes] = useState([])
  const [geneInput, setGeneInput] = useState('')
  const [suggestions, setSuggestions] = useState([])
  const [secondary, setSecondary] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    let active = true
    getPathologyCatalog().then((data) => { if (active) setCatalog(data) })
      .catch((failure) => { if (active) setCatalogError(errorMessage(failure)) })
    return () => { active = false }
  }, [])

  useEffect(() => {
    if (!reanalysis) return undefined
    let active = true
    getStudyRequest(studyId).then((data) => { if (active) setOrigin(data) })
      .catch((failure) => { if (active) setOriginError(errorMessage(failure)) })
    return () => { active = false }
  }, [reanalysis, studyId])

  // Paciente precargado desde la ficha (?paciente=ID): se busca por DNI/nombre al escribir.
  useEffect(() => {
    if (reanalysis) return undefined
    const controller = new AbortController()
    const timer = setTimeout(async () => {
      try {
        const result = await listPatients(patientQuery, 0, controller.signal)
        if (!controller.signal.aborted) {
          setPatientResults(result.items)
          const preset = Number(params.get('paciente'))
          if (preset && !patient) {
            const found = result.items.find((item) => item.id === preset)
            if (found) setPatient(found)
          }
        }
      } catch { /* la búsqueda se reintenta al seguir escribiendo */ }
    }, 250)
    return () => { clearTimeout(timer); controller.abort() }
  }, [patientQuery, params, patient, reanalysis])

  useEffect(() => {
    const term = geneInput.trim()
    if (term.length < 2) { setSuggestions([]); return undefined }
    let active = true
    const timer = setTimeout(() => {
      searchGenes(term).then((data) => { if (active) setSuggestions(data.slice(0, 12)) }).catch(() => { if (active) setSuggestions([]) })
    }, 250)
    return () => { active = false; clearTimeout(timer) }
  }, [geneInput])

  // En un reanálisis no se repiten genes ya analizados en ese exoma (entrevista con el PO).
  const analyzed = useMemo(() => new Set(origin?.analyzed_genes || []), [origin])
  const pathologyGenes = useMemo(() => {
    const symbols = new Set()
    for (const item of catalog || []) if (codes.includes(item.code)) item.genes.forEach((gene) => symbols.add(gene))
    return [...symbols]
  }, [catalog, codes])
  const catalogGenes = pathologyGenes.filter((gene) => !analyzed.has(gene))
  const skippedGenes = pathologyGenes.filter((gene) => analyzed.has(gene))
  const extras = extraGenes.filter((gene) => !catalogGenes.includes(gene))
  const totalGenes = catalogGenes.length + extras.length
  const canSubmit = (reanalysis ? Boolean(origin) : Boolean(patient) && codes.length > 0) && totalGenes > 0 && !submitting
  const backTo = reanalysis ? `/estudios/${studyId}` : '/estudios'

  function toggleCode(code) { setCodes((current) => current.includes(code) ? current.filter((item) => item !== code) : [...current, code]) }
  function addGene(symbol) {
    const value = symbol.trim().toUpperCase()
    if (!value) return
    if (analyzed.has(value)) { setGeneNotice(`${value} ya se analizó en este exoma.`); return }
    setGeneNotice('')
    setExtraGenes((current) => current.includes(value) ? current : [...current, value])
    setGeneInput(''); setSuggestions([])
  }

  async function submit(event) {
    event.preventDefault()
    if (!canSubmit) return
    setSubmitting(true); setError('')
    try {
      const created = reanalysis
        ? await requestReanalysis(studyId, { pathology_codes: codes, additional_genes: extras, include_secondary_findings: secondary })
        : await createStudyRequest({ patient_id: patient.id, pathology_codes: codes, additional_genes: extras, include_secondary_findings: secondary })
      navigate(`/estudios/${created.id}`)
    } catch (failure) {
      setError(errorMessage(failure)); setSubmitting(false)
    }
  }

  if (reanalysis && originError) {
    return <ClinicalLayout session={session} pageLabel="Reanálisis"><section className="est-page">
      <Link to={backTo} className="est-back"><ArrowLeft size={14} aria-hidden="true" />Volver al estudio</Link>
      <div role="alert" className="est-error"><p>{originError}</p></div>
    </section></ClinicalLayout>
  }

  return <ClinicalLayout session={session} pageLabel={reanalysis ? 'Reanálisis' : 'Nueva solicitud'}><section className="est-page">
    <Link to={backTo} className="est-back"><ArrowLeft size={14} aria-hidden="true" />{reanalysis ? 'Volver al estudio' : 'Volver a las solicitudes'}</Link>
    {reanalysis
      ? <header className="est-header"><div><span className="est-eyebrow">REANÁLISIS DEL ESTUDIO #{studyId}</span><h1>Solicitar reanálisis</h1><p>Se vuelve a analizar el mismo exoma con otros genes: no hace falta extracción ni envío. Tiene un {REANALYSIS_DISCOUNT_PERCENT} % de descuento y no admite cupones.</p></div></header>
      : <header className="est-header"><div><span className="est-eyebrow">SOLICITUD DE ESTUDIO</span><h1>Nueva solicitud</h1><p>Elegí el paciente y las patologías sospechadas. Los genes se completan solos y podés sumar los que necesites.</p></div></header>}
    <form onSubmit={submit} className="est-grid">
      <div className="est-stack">
        <section className="est-card" aria-labelledby="est-patient-title">
          <h2 id="est-patient-title">1. Paciente</h2>
          {reanalysis ? (!origin ? <p role="status" className="est-loading">Cargando estudio de origen...</p>
            : <>
              <p className="est-help" style={{ marginTop: 0 }}>{origin.patient_name || `Paciente ${origin.patient_id}`} · estudio de origen #{origin.id}</p>
              <h3>Ya analizados en este exoma</h3>
              <ul className="est-chips" aria-label="Genes ya analizados">{origin.analyzed_genes.map((gene) => <li key={gene} className="est-chip est-chip-muted">{gene}</li>)}</ul>
              <p className="est-help">Estos genes no se vuelven a pedir.</p>
            </>)
            : patient ? <div className="est-chips"><span className="est-chip est-chip-catalog">{patient.last_name}, {patient.first_name} · DNI {patient.dni}<button type="button" aria-label="Quitar paciente" onClick={() => setPatient(null)}><X size={13} aria-hidden="true" /></button></span></div>
            : <>
              <label htmlFor="est-patient-search">Buscar paciente</label>
              <input id="est-patient-search" type="search" maxLength={100} value={patientQuery} placeholder="Nombre, apellido o DNI" onChange={(event) => setPatientQuery(event.target.value)} />
              {patientResults.length === 0 ? <p className="est-help"><Search size={12} aria-hidden="true" /> No hay pacientes para esa búsqueda. Primero registrá al paciente desde Pacientes.</p>
                : <ul className="est-patient-results">{patientResults.map((item) => <li key={item.id}><button type="button" aria-pressed="false" onClick={() => setPatient(item)}><span>{item.last_name}, {item.first_name}</span><small>DNI {item.dni}</small></button></li>)}</ul>}
            </>}
        </section>

        <section className="est-card" aria-labelledby="est-path-title">
          <h2 id="est-path-title">2. Patologías sospechadas{reanalysis && ' (opcional)'}</h2>
          {catalogError ? <div role="alert" className="est-error"><p>{catalogError}</p></div>
            : !catalog ? <p role="status" className="est-loading">Cargando catálogo...</p>
              : <fieldset style={{ border: 0, padding: 0, margin: 0 }}><legend className="est-sr-only">Patologías</legend><div className="est-options">
                {catalog.map((item) => <label key={item.code} className={`est-option ${codes.includes(item.code) ? 'est-selected' : ''}`}>
                  <input type="checkbox" checked={codes.includes(item.code)} onChange={() => toggleCode(item.code)} />
                  <span><strong>{item.name}</strong><small>{item.genes.length ? item.genes.join(', ') : 'Sin genes asociados'}</small></span>
                </label>)}
              </div></fieldset>}
        </section>

        <section className="est-card" aria-labelledby="est-genes-title">
          <h2 id="est-genes-title">3. Genes a analizar</h2>
          {skippedGenes.length > 0 && <p className="est-help">No se incluyen porque ya se analizaron: {skippedGenes.join(', ')}.</p>}
          {totalGenes === 0 ? <p className="est-help">{reanalysis ? 'Elegí una patología o agregá al menos un gen que no se haya analizado.' : 'Elegí al menos una patología con genes asociados.'}</p>
            : <ul className="est-chips" aria-label="Genes seleccionados">
              {catalogGenes.map((gene) => <li key={gene} className="est-chip est-chip-catalog"><Dna size={12} aria-hidden="true" />{gene}</li>)}
              {extras.map((gene) => <li key={gene} className="est-chip">{gene}<button type="button" aria-label={`Quitar ${gene}`} onClick={() => setExtraGenes((current) => current.filter((item) => item !== gene))}><X size={13} aria-hidden="true" /></button></li>)}
            </ul>}
          <h3>Agregar genes adicionales</h3>
          <label htmlFor="est-gene-input">Símbolo del gen</label>
          <div style={{ display: 'flex', gap: 8 }}>
            <input id="est-gene-input" value={geneInput} maxLength={50} placeholder="Ej. NOTCH3, GLA, GAA" autoComplete="off" onChange={(event) => setGeneInput(event.target.value)} onKeyDown={(event) => { if (event.key === 'Enter') { event.preventDefault(); addGene(geneInput) } }} />
            <button type="button" onClick={() => addGene(geneInput)} disabled={!geneInput.trim()}><Plus size={14} aria-hidden="true" />Agregar</button>
          </div>
          {geneNotice && <p className="est-help" role="alert" style={{ color: '#9f1239' }}>{geneNotice}</p>}
          {suggestions.length > 0 && <ul className="est-suggestions" aria-label="Sugerencias de genes">{suggestions.map((symbol) => <li key={symbol}><button type="button" disabled={analyzed.has(symbol)} title={analyzed.has(symbol) ? 'Ya analizado en este exoma' : undefined} onClick={() => addGene(symbol)}>{symbol}</button></li>)}</ul>}
          <p className="est-help">El gen se valida contra Apigen al crear la solicitud; un mismo gen no se repite aunque pertenezca a varias patologías.</p>
          <label className={`est-option ${secondary ? 'est-selected' : ''}`} style={{ marginTop: 16 }}>
            <input type="checkbox" checked={secondary} onChange={(event) => setSecondary(event.target.checked)} />
            <span><strong>Incluir búsqueda de hallazgos secundarios</strong><small>No modifica el precio del presupuesto.</small></span>
          </label>
        </section>
      </div>

      <aside className="est-aside" aria-label="Resumen">
        <section className="est-card">
          <h2>Resumen</h2>
          <dl className="est-dl">
            <dt>Paciente</dt><dd>{reanalysis ? (origin?.patient_name || '—') : patient ? `${patient.last_name}, ${patient.first_name}` : 'Sin elegir'}</dd>
            <dt>Patologías</dt><dd>{codes.length || 'Sin elegir'}</dd>
            <dt>Genes</dt><dd>{totalGenes}</dd>
            <dt>Presupuesto estimado</dt><dd>{totalGenes ? money(estimateTotalCents(totalGenes, reanalysis)) : '—'}<small>USD 500 hasta 5 genes, más USD 30 por cada gen adicional{reanalysis ? `, con ${REANALYSIS_DISCOUNT_PERCENT} % de descuento por reanálisis` : ''}. El presupuesto oficial lo emite administración.</small></dd>
          </dl>
          {error && <div role="alert" className="est-error" style={{ marginTop: 16 }}><AlertCircle size={15} aria-hidden="true" /><p>{error}</p></div>}
          <div className="est-actions"><button type="submit" className="est-primary" disabled={!canSubmit}>{submitting ? 'Enviando...' : reanalysis ? 'Solicitar reanálisis' : 'Crear solicitud'}</button></div>
        </section>
      </aside>
    </form>
  </section></ClinicalLayout>
}
