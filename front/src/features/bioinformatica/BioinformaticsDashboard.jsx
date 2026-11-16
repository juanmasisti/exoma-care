import { useCallback, useEffect, useMemo, useState } from 'react'
import { Activity, AlertCircle, CalendarDays, CheckCircle2, ClipboardList, Dna, History, Mail, RefreshCw, Search, UserRound } from 'lucide-react'
import { useSearchParams } from 'react-router-dom'
import ClinicalLayout from '../../components/layout/ClinicalLayout.jsx'
import PatologiaSelect from './components/PatologiaSelect.jsx'
import { api, errorMessage } from '../../services/api.js'
import { fetchBioinformaticsHistory, fetchBioinformaticsStudies } from '../../services/bioinformaticaService.js'
import './bioinformatics.css'

const SECTIONS = new Set(['inicio', 'disponibles', 'analisis', 'historial'])
const BIOINFORMATICS_AVAILABLE = 'en_area_bioinformatica'
const BIOINFORMATICS_ACTIVE = 'en_analisis'
const BIOINFORMATICS_COMPLETE = 'resultado_disponible'

function displayDate(value) {
  if (!value) return null
  const dateOnly = typeof value === 'string' && /^(\d{4})-(\d{2})-(\d{2})$/.exec(value)
  const date = dateOnly
    ? new Date(Number(dateOnly[1]), Number(dateOnly[2]) - 1, Number(dateOnly[3]))
    : new Date(value)
  return Number.isNaN(date.getTime()) ? String(value) : date.toLocaleString('es-AR')
}

function displayValue(value) {
  if (value === null || value === undefined || value === '') return null
  if (typeof value === 'boolean') return value ? 'Sí' : 'No'
  if (Array.isArray(value)) return value.length ? value : null
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}

function PatientDetails({ patient }) {
  if (!patient) return <p className="bioinformatics-muted">No hay información del paciente asociada a este estudio.</p>

  const fields = [
    ['Documento', patient.dni],
    ['Fecha de nacimiento', displayDate(patient.fecha_nacimiento)],
    ['Correo', patient.email],
    ['Teléfono', patient.telefono],
    ['Tipo de sospecha', patient.suspicion_type],
    ['Resumen clínico', patient.clinical_summary],
    ['Antecedentes familiares', patient.family_history],
    ['Alta de ficha', displayDate(patient.created_at)],
    ['Última actualización', displayDate(patient.updated_at)],
  ].filter(([, value]) => displayValue(value))

  const revision = patient.clinical_revision || {}
  const symptoms = revision.symptoms || []
  const suspicions = revision.suspicions || []
  const physician = patient.physician

  return <div className="bioinformatics-patient-details">
    <div className="bioinformatics-data-grid">
      {fields.map(([label, value]) => <div key={label} className="bioinformatics-data-field">
        <span>{label}</span><strong>{displayValue(value)}</strong>
      </div>)}
    </div>
    {physician && <section className="bioinformatics-related-record">
      <h3>Médico tratante</h3>
      <p>{[physician.nombre, physician.apellido].filter(Boolean).join(' ')}</p>
      {[physician.specialty, physician.license_number, physician.email].filter(Boolean).map((value) => <small key={value}>{value}</small>)}
    </section>}
    {symptoms.length > 0 && <section className="bioinformatics-related-record">
      <h3>Síntomas registrados</h3>
      <ul>{symptoms.map((item, index) => <li key={`${item.id ?? item.code ?? item.name ?? index}`}>
        {[item.label, item.name, item.code].filter(Boolean).join(' · ') || displayValue(item)}
      </li>)}</ul>
    </section>}
    {suspicions.length > 0 && <section className="bioinformatics-related-record">
      <h3>Sospechas clínicas registradas</h3>
      <ul>{suspicions.map((item, index) => <li key={`${item.pathology_id ?? item.code ?? index}`}>
        {[item.pathology_name, item.name, item.code, item.rationale].filter(Boolean).join(' · ') || displayValue(item)}
      </li>)}</ul>
    </section>}
  </div>
}

function StudyResult({ study }) {
  return <div className="bioinformatics-result-details">
    {study.codigo_patologia && <p><strong>Código de patología:</strong> {study.codigo_patologia}</p>}
    {study.resultado_diagnostico && <p><strong>Diagnóstico registrado:</strong> {study.resultado_diagnostico}</p>}
    {study.variantes_detectadas?.length > 0 && <section>
      <h3>Variantes registradas</h3>
      <ul className="bioinformatics-variant-list">{study.variantes_detectadas.map((variant, index) => <li key={variant.id ?? `${variant.gen}-${variant.hgvs_c}-${index}`}>
        <strong>{[variant.gen, variant.hgvs_c, variant.proteina].filter(Boolean).join(' · ')}</strong>
        {variant.clasificacion && <small>{variant.clasificacion}</small>}
      </li>)}</ul>
    </section>}
    {study.hallazgos_secundarios?.length > 0 && <section>
      <h3>Hallazgos secundarios</h3>
      <ul>{study.hallazgos_secundarios.map((finding, index) => <li key={finding.id ?? index}>{displayValue(finding)}</li>)}</ul>
    </section>}
    {study.fecha_reevaluacion && <p><strong>Fecha de reevaluación:</strong> {displayDate(study.fecha_reevaluacion)}</p>}
  </div>
}

function StudyCard({ study, onSelect, actionLabel, disabled, statusLabel, onResendNotification, resending }) {
  return <article className="bioinformatics-study-card">
    <div className="bioinformatics-study-card-main">
      <div className="bioinformatics-study-title">
        <span className="bioinformatics-study-icon"><Dna size={18} aria-hidden="true" /></span>
        <div><h3>Estudio #{study.id}</h3><span>{study.patient_name}</span></div>
      </div>
      <span className={`bioinformatics-status ${study.status === BIOINFORMATICS_COMPLETE ? 'is-complete' : ''}`}>{statusLabel}</span>
    </div>
    <div className="bioinformatics-study-meta">
      {study.patient_dni && <span>Documento: {study.patient_dni}</span>}
      {study.created_at && <span><CalendarDays size={14} aria-hidden="true" />{displayDate(study.created_at)}</span>}
      {study.analyst_id && <span>Bioinformático asignado: #{study.analyst_id}</span>}
      {study.codigo_patologia && <span>Patología: {study.codigo_patologia}</span>}
    </div>
    {study.patient && <details className="bioinformatics-details">
      <summary><UserRound size={15} aria-hidden="true" /> Datos del paciente</summary>
      <PatientDetails patient={study.patient} />
    </details>}
    {study.status === BIOINFORMATICS_COMPLETE && <StudyResult study={study} />}
    {(onSelect || onResendNotification) && <div className="bioinformatics-study-actions">
      {onResendNotification && <button type="button" disabled={resending} onClick={() => onResendNotification(study)}>
        <Mail size={15} aria-hidden="true" />{resending ? 'Reenviando...' : 'Reenviar aviso'}
      </button>}
      {onSelect && <button type="button" className="bioinformatics-primary" disabled={disabled} onClick={() => onSelect(study)}>{actionLabel}</button>}
    </div>}
  </article>
}

function EmptyState({ children }) {
  return <div className="bioinformatics-empty"><Activity size={25} aria-hidden="true" /><p>{children}</p></div>
}

export default function BioinformaticsDashboard({ session }) {
  const [searchParams, setSearchParams] = useSearchParams()
  const requestedSection = searchParams.get('section') || 'inicio'
  const section = SECTIONS.has(requestedSection) ? requestedSection : 'inicio'
  const [studies, setStudies] = useState([])
  const [history, setHistory] = useState([])
  const [historyQuery, setHistoryQuery] = useState('')
  const [historySearch, setHistorySearch] = useState('')
  const [selectedStudy, setSelectedStudy] = useState(null)
  const [gene, setGene] = useState('')
  const [hgvs, setHgvs] = useState('')
  const [pathology, setPathology] = useState('')
  const [variants, setVariants] = useState([])
  const [selectedVariants, setSelectedVariants] = useState([])
  const [loadingStudies, setLoadingStudies] = useState(true)
  const [loadingHistory, setLoadingHistory] = useState(true)
  const [loadingVariants, setLoadingVariants] = useState(false)
  const [busy, setBusy] = useState(false)
  const [resendingStudyId, setResendingStudyId] = useState(null)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')

  const availableStudies = useMemo(
    () => studies.filter((study) => study.status === BIOINFORMATICS_AVAILABLE),
    [studies],
  )
  const analyzingStudies = useMemo(
    () => studies.filter((study) => study.status === BIOINFORMATICS_ACTIVE),
    [studies],
  )
  const visibleStudies = useMemo(() => {
    const list = section === 'disponibles' ? availableStudies : analyzingStudies
    const query = historyQuery.trim().toLocaleLowerCase()
    if (!query) return list
    return list.filter((study) => [
      study.patient_name,
      study.patient_dni,
      String(study.id),
      study.codigo_patologia,
    ].filter(Boolean).some((value) => String(value).toLocaleLowerCase().includes(query)))
  }, [availableStudies, analyzingStudies, historyQuery, section])

  const loadStudies = useCallback(async (showLoading = false) => {
    if (showLoading) setLoadingStudies(true)
    try {
      setStudies(await fetchBioinformaticsStudies())
    } catch (failure) {
      setError(errorMessage(failure))
    } finally {
      setLoadingStudies(false)
    }
  }, [])

  const loadHistory = useCallback(async (query = '', showLoading = false) => {
    if (showLoading) setLoadingHistory(true)
    try {
      setHistory(await fetchBioinformaticsHistory(query))
      setError('')
    } catch (failure) {
      setError(errorMessage(failure))
    } finally {
      setLoadingHistory(false)
    }
  }, [])

  useEffect(() => {
    let active = true
    fetchBioinformaticsStudies()
      .then((data) => { if (active) setStudies(data) })
      .catch((failure) => { if (active) setError(errorMessage(failure)) })
      .finally(() => { if (active) setLoadingStudies(false) })
    fetchBioinformaticsHistory()
      .then((data) => { if (active) setHistory(data) })
      .catch((failure) => { if (active) setError(errorMessage(failure)) })
      .finally(() => { if (active) setLoadingHistory(false) })
    return () => { active = false }
  }, [])

  function navigateTo(nextSection) {
    setSearchParams({ section: nextSection })
    setError('')
    setNotice('')
  }

  async function refresh() {
    setError('')
    await Promise.all([loadStudies(true), loadHistory(historySearch, true)])
  }

  async function startAnalysis(study) {
    setBusy(true)
    setError('')
    setNotice('')
    try {
      const { data } = await api.patch(`/bioinformatica/estudios/${study.id}/iniciar`)
      setStudies((current) => current.map((item) => item.id === data.id ? data : item))
      setSelectedStudy(data)
      setPathology(data.codigo_patologia || '')
      navigateTo('analisis')
      setNotice(`Estudio #${data.id} asignado para análisis.`)
    } catch (failure) {
      setError(errorMessage(failure))
      await loadStudies()
    } finally {
      setBusy(false)
    }
  }

  function selectStudy(study) {
    setSelectedStudy(study)
    setPathology(study.codigo_patologia || '')
    setVariants([])
    setSelectedVariants([])
    setError('')
    setNotice('')
  }

  async function searchVariants(event) {
    event.preventDefault()
    setLoadingVariants(true)
    setError('')
    setNotice('')
    setSelectedVariants([])
    try {
      const { data } = await api.get('/bioinformatica/variantes', {
        params: { gen: gene.trim(), hgvs_c: hgvs.trim() || undefined, limit: 50, offset: 0 },
      })
      setVariants(data.items.map((variant) => ({ ...variant, gen: gene.trim() })))
    } catch (failure) {
      setError(errorMessage(failure))
    } finally {
      setLoadingVariants(false)
    }
  }

  function toggleVariant(variant) {
    setSelectedVariants((current) => current.some((item) => item.id === variant.id)
      ? current.filter((item) => item.id !== variant.id)
      : [...current, variant])
  }

  async function submitResult(event) {
    event.preventDefault()
    if (!selectedStudy) return
    setBusy(true)
    setError('')
    setNotice('')
    try {
      const { data } = await api.post(
        `/bioinformatica/estudios/${selectedStudy.id}/resultados`,
        { codigo_patologia: pathology.trim(), variantes: selectedVariants },
      )
      setStudies((current) => current.filter((item) => item.id !== data.id))
      setSelectedStudy(null)
      setSelectedVariants([])
      setVariants([])
      setNotice(`Resultado del estudio #${data.id} guardado correctamente.`)
      await Promise.all([loadStudies(true), loadHistory(historySearch, true)])
      navigateTo('historial')
    } catch (failure) {
      setError(errorMessage(failure))
      await loadStudies()
    } finally {
      setBusy(false)
    }
  }

  async function searchHistory(event) {
    event.preventDefault()
    setHistorySearch(historyQuery)
    await loadHistory(historyQuery, true)
  }

  async function resendResultNotification(study) {
    setResendingStudyId(study.id)
    setError('')
    setNotice('')
    try {
      await api.post(`/bioinformatica/estudios/${study.id}/reenviar-notificacion`)
      setNotice(`Se reenvió el aviso de resultado disponible del estudio #${study.id} al paciente y al médico tratante.`)
    } catch (failure) {
      setError(errorMessage(failure))
    } finally {
      setResendingStudyId(null)
    }
  }

  const counts = {
    total: studies.length,
    available: availableStudies.length,
    analyzing: analyzingStudies.length,
    history: history.length,
  }
  const sectionTitles = {
    inicio: ['Inicio / Dashboard', 'Resumen de los estudios guardados para análisis bioinformático.'],
    disponibles: ['Estudios disponibles', 'Estudios del paciente que están en el área de bioinformática.'],
    analisis: ['En análisis', 'Estudios asignados y resultados que se están completando.'],
    historial: ['Historial', 'Estudios previos y resultados almacenados en la base de datos.'],
  }
  const [title, description] = sectionTitles[section]

  return <ClinicalLayout session={session} bioinformaticsCounts={counts} pageLabel={selectedStudy ? `Estudio #${selectedStudy.id}` : null}>
    <main className="bioinformatics-page">
      <header className="bioinformatics-header">
        <div>
          <p className="bioinformatics-eyebrow">ÁREA DE BIOINFORMÁTICA</p>
          <h1>{title}</h1>
          <p>{description}</p>
        </div>
        <button type="button" className="bioinformatics-secondary" onClick={refresh} disabled={loadingStudies || loadingHistory || busy || resendingStudyId !== null}>
          <RefreshCw size={16} aria-hidden="true" />Actualizar
        </button>
      </header>

      {error && <p className="bioinformatics-error" role="alert"><AlertCircle size={17} aria-hidden="true" />{error}</p>}
      {notice && <p className="bioinformatics-notice" role="status"><CheckCircle2 size={17} aria-hidden="true" />{notice}</p>}

      {section === 'inicio' && <section className="bioinformatics-dashboard-content">
        <div className="bioinformatics-stats">
          <button type="button" className="bioinformatics-stat" onClick={() => navigateTo('disponibles')}>
            <span>Estudios disponibles</span><strong>{loadingStudies ? '—' : availableStudies.length}</strong><small>En el área de bioinformática</small>
          </button>
          <button type="button" className="bioinformatics-stat" onClick={() => navigateTo('analisis')}>
            <span>En análisis</span><strong>{loadingStudies ? '—' : analyzingStudies.length}</strong><small>En curso o asignados</small>
          </button>
          <button type="button" className="bioinformatics-stat" onClick={() => navigateTo('historial')}>
            <span>Historial de estudios</span><strong>{loadingHistory ? '—' : history.length}</strong><small>Resultados previos guardados</small>
          </button>
        </div>
        <section className="bioinformatics-section">
          <div className="bioinformatics-section-heading"><div><h2>Estudios de la bandeja</h2><p>Datos actuales de los estudios asociados a cada paciente.</p></div></div>
          {loadingStudies ? <p role="status" className="bioinformatics-empty">Cargando estudios desde la base de datos...</p>
            : studies.length === 0 ? <EmptyState>No hay estudios disponibles ni en análisis.</EmptyState>
              : <div className="bioinformatics-cards">{studies.map((study) => <StudyCard
                key={study.id}
                study={study}
                statusLabel={study.status === BIOINFORMATICS_AVAILABLE ? 'Disponible' : 'En análisis'}
                onSelect={study.status === BIOINFORMATICS_AVAILABLE
                  ? startAnalysis
                  : study.analyst_id === null || study.analyst_id === session.user_id ? selectStudy : null}
                actionLabel={study.status === BIOINFORMATICS_AVAILABLE ? 'Tomar estudio' : 'Abrir estudio'}
                disabled={busy || (study.status === BIOINFORMATICS_ACTIVE && study.analyst_id !== null && study.analyst_id !== session.user_id)}
              />)}</div>}
        </section>
      </section>}

      {(section === 'disponibles' || section === 'analisis') && <section className="bioinformatics-section">
        <div className="bioinformatics-section-heading">
          <div><h2>{section === 'disponibles' ? 'Estudios disponibles' : 'Estudios en análisis'}</h2><p>{visibleStudies.length} registro(s) de la base de datos.</p></div>
          <form className="bioinformatics-filter" onSubmit={(event) => event.preventDefault()}>
            <Search size={16} aria-hidden="true" />
            <label className="bioinformatics-visually-hidden" htmlFor="active-study-search">Filtrar estudios</label>
            <input id="active-study-search" value={historyQuery} onChange={(event) => setHistoryQuery(event.target.value)} placeholder="Buscar por paciente, documento o estudio" />
          </form>
        </div>
        {loadingStudies ? <p role="status" className="bioinformatics-empty">Cargando estudios desde la base de datos...</p>
          : visibleStudies.length === 0 ? <EmptyState>{section === 'disponibles' ? 'No hay estudios disponibles que coincidan con la búsqueda.' : 'No hay estudios en análisis que coincidan con la búsqueda.'}</EmptyState>
            : <div className="bioinformatics-cards">{visibleStudies.map((study) => <StudyCard
              key={study.id}
              study={study}
              statusLabel={study.status === BIOINFORMATICS_AVAILABLE ? 'Disponible' : 'En análisis'}
              onSelect={section === 'disponibles'
                ? startAnalysis
                : study.analyst_id === null || study.analyst_id === session.user_id ? selectStudy : null}
              actionLabel={section === 'disponibles' ? 'Tomar estudio' : 'Abrir estudio'}
              disabled={busy || (section === 'analisis' && study.analyst_id !== null && study.analyst_id !== session.user_id)}
            />)}</div>}
        {section === 'analisis' && selectedStudy && <section className="bioinformatics-section bioinformatics-analysis-panel">
          <div className="bioinformatics-section-heading">
            <div><h2>Completar estudio #{selectedStudy.id}</h2><p>{selectedStudy.patient_name} · DNI {selectedStudy.patient_dni}</p></div>
          </div>
          <PatientDetails patient={selectedStudy.patient} />
          <form className="bioinformatics-search-form" onSubmit={searchVariants}>
            <label htmlFor="bioinformatics-gene">Gen para consultar en Apigen</label>
            <input id="bioinformatics-gene" value={gene} onChange={(event) => setGene(event.target.value)} required maxLength={50} placeholder="Ingresá el símbolo del gen" />
            <label htmlFor="bioinformatics-hgvs">HGVS c (opcional)</label>
            <input id="bioinformatics-hgvs" value={hgvs} onChange={(event) => setHgvs(event.target.value)} maxLength={100} placeholder="Ingresá la variante HGVS c" />
            <button type="submit" className="bioinformatics-primary" disabled={loadingVariants || busy}>
              <Search size={15} aria-hidden="true" />{loadingVariants ? 'Buscando...' : 'Buscar variantes'}
            </button>
          </form>
          {variants.length > 0 && <form className="bioinformatics-results-form" onSubmit={submitResult}>
            <PatologiaSelect value={pathology} onChange={(event) => setPathology(event.target.value)} required />
            <ul className="bioinformatics-variant-list">{variants.map((variant) => <li key={variant.id}>
              <label><input type="checkbox" checked={selectedVariants.some((item) => item.id === variant.id)} onChange={() => toggleVariant(variant)} />
                <span><strong>{variant.gen}: {variant.hgvs_c}</strong><small>{variant.proteina || 'Sin dato proteico'} · {variant.clasificacion}</small></span></label>
            </li>)}</ul>
            <p className="bioinformatics-muted">Seleccionadas: {selectedVariants.length}</p>
            <button type="submit" className="bioinformatics-primary" disabled={!selectedVariants.length || !pathology || busy}>
              {busy ? 'Guardando...' : `Guardar resultado del estudio #${selectedStudy.id}`}
            </button>
          </form>}
        </section>}
      </section>}

      {section === 'historial' && <section className="bioinformatics-section">
        <div className="bioinformatics-section-heading">
          <div><h2>Historial de estudios</h2><p>Se muestran estudios previos que tienen resultado registrado.</p></div>
          <form className="bioinformatics-filter" onSubmit={searchHistory}>
            <Search size={16} aria-hidden="true" />
            <label className="bioinformatics-visually-hidden" htmlFor="history-search">Buscar en el historial</label>
            <input id="history-search" value={historyQuery} onChange={(event) => setHistoryQuery(event.target.value)} placeholder="Buscar por paciente, documento o estudio" />
            <button type="submit" disabled={loadingHistory}><Search size={15} aria-hidden="true" />Buscar</button>
          </form>
        </div>
        {loadingHistory ? <p role="status" className="bioinformatics-empty">Cargando historial desde la base de datos...</p>
          : history.length === 0 ? <EmptyState>No hay estudios previos con resultados registrados.</EmptyState>
            : <div className="bioinformatics-cards">{history.map((study) => <StudyCard
              key={study.id}
              study={study}
              statusLabel={study.status === BIOINFORMATICS_COMPLETE ? 'Resultado disponible' : study.status}
              onResendNotification={resendResultNotification}
              resending={resendingStudyId === study.id}
              disabled={resendingStudyId !== null}
            />)}</div>}
      </section>}

      {section === 'analisis' && !selectedStudy && !loadingStudies && analyzingStudies.length > 0 && <p className="bioinformatics-selection-hint"><ClipboardList size={16} aria-hidden="true" />Seleccioná un estudio asignado a tu usuario para continuar.</p>}
      {section === 'historial' && <p className="bioinformatics-history-note"><History size={15} aria-hidden="true" />El contenido se obtiene de los registros asociados a cada paciente y estudio.</p>}
    </main>
  </ClinicalLayout>
}
