import { useEffect, useMemo, useState } from 'react'
import { AlertCircle, ArrowLeft, Dna, Plus, Search, X } from 'lucide-react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import ClinicalLayout from '../../components/layout/ClinicalLayout.jsx'
import { errorMessage } from '../../services/api.js'
import { listPatients } from '../pacientes/api.js'
import { createStudyRequest, getPathologyCatalog, searchGenes } from './api.js'
import { estimateTotalCents, money } from './format.js'
import './estudios.css'

export default function NuevaSolicitud({ session }) {
  const navigate = useNavigate()
  const [params] = useSearchParams()
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

  // Paciente precargado desde la ficha (?paciente=ID): se busca por DNI/nombre al escribir.
  useEffect(() => {
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
  }, [patientQuery, params, patient])

  useEffect(() => {
    const term = geneInput.trim()
    if (term.length < 2) { setSuggestions([]); return undefined }
    let active = true
    const timer = setTimeout(() => {
      searchGenes(term).then((data) => { if (active) setSuggestions(data.slice(0, 12)) }).catch(() => { if (active) setSuggestions([]) })
    }, 250)
    return () => { active = false; clearTimeout(timer) }
  }, [geneInput])

  const catalogGenes = useMemo(() => {
    const symbols = new Set()
    for (const item of catalog || []) if (codes.includes(item.code)) item.genes.forEach((gene) => symbols.add(gene))
    return [...symbols]
  }, [catalog, codes])
  const extras = extraGenes.filter((gene) => !catalogGenes.includes(gene))
  const totalGenes = catalogGenes.length + extras.length
  const canSubmit = Boolean(patient) && codes.length > 0 && totalGenes > 0 && !submitting

  function toggleCode(code) { setCodes((current) => current.includes(code) ? current.filter((item) => item !== code) : [...current, code]) }
  function addGene(symbol) {
    const value = symbol.trim().toUpperCase()
    if (!value) return
    setExtraGenes((current) => current.includes(value) ? current : [...current, value])
    setGeneInput(''); setSuggestions([])
  }

  async function submit(event) {
    event.preventDefault()
    if (!canSubmit) return
    setSubmitting(true); setError('')
    try {
      const created = await createStudyRequest({ patient_id: patient.id, pathology_codes: codes, additional_genes: extras, include_secondary_findings: secondary })
      navigate(`/estudios/${created.id}`)
    } catch (failure) {
      setError(errorMessage(failure)); setSubmitting(false)
    }
  }

  return <ClinicalLayout session={session} pageLabel="Nueva solicitud"><section className="est-page">
    <Link to="/estudios" className="est-back"><ArrowLeft size={14} aria-hidden="true" />Volver a las solicitudes</Link>
    <header className="est-header"><div><span className="est-eyebrow">SOLICITUD DE ESTUDIO</span><h1>Nueva solicitud</h1><p>Elegí el paciente y las patologías sospechadas. Los genes se completan solos y podés sumar los que necesites.</p></div></header>
    <form onSubmit={submit} className="est-grid">
      <div className="est-stack">
        <section className="est-card" aria-labelledby="est-patient-title">
          <h2 id="est-patient-title">1. Paciente</h2>
          {patient ? <div className="est-chips"><span className="est-chip est-chip-catalog">{patient.last_name}, {patient.first_name} · DNI {patient.dni}<button type="button" aria-label="Quitar paciente" onClick={() => setPatient(null)}><X size={13} aria-hidden="true" /></button></span></div>
            : <>
              <label htmlFor="est-patient-search">Buscar paciente</label>
              <input id="est-patient-search" type="search" maxLength={100} value={patientQuery} placeholder="Nombre, apellido o DNI" onChange={(event) => setPatientQuery(event.target.value)} />
              {patientResults.length === 0 ? <p className="est-help"><Search size={12} aria-hidden="true" /> No hay pacientes para esa búsqueda. Primero registrá al paciente desde Pacientes.</p>
                : <ul className="est-patient-results">{patientResults.map((item) => <li key={item.id}><button type="button" aria-pressed="false" onClick={() => setPatient(item)}><span>{item.last_name}, {item.first_name}</span><small>DNI {item.dni}</small></button></li>)}</ul>}
            </>}
        </section>

        <section className="est-card" aria-labelledby="est-path-title">
          <h2 id="est-path-title">2. Patologías sospechadas</h2>
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
          {totalGenes === 0 ? <p className="est-help">Elegí al menos una patología con genes asociados.</p>
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
          {suggestions.length > 0 && <ul className="est-suggestions" aria-label="Sugerencias de genes">{suggestions.map((symbol) => <li key={symbol}><button type="button" onClick={() => addGene(symbol)}>{symbol}</button></li>)}</ul>}
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
            <dt>Paciente</dt><dd>{patient ? `${patient.last_name}, ${patient.first_name}` : 'Sin elegir'}</dd>
            <dt>Patologías</dt><dd>{codes.length || 'Sin elegir'}</dd>
            <dt>Genes</dt><dd>{totalGenes}</dd>
            <dt>Presupuesto estimado</dt><dd>{totalGenes ? money(estimateTotalCents(totalGenes)) : '—'}<small>USD 500 hasta 5 genes, más USD 30 por cada gen adicional. El presupuesto oficial lo emite administración.</small></dd>
          </dl>
          {error && <div role="alert" className="est-error" style={{ marginTop: 16 }}><AlertCircle size={15} aria-hidden="true" /><p>{error}</p></div>}
          <div className="est-actions"><button type="submit" className="est-primary" disabled={!canSubmit}>{submitting ? 'Creando...' : 'Crear solicitud'}</button></div>
        </section>
      </aside>
    </form>
  </section></ClinicalLayout>
}
