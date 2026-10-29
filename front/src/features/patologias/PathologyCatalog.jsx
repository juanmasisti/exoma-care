import { useEffect, useState } from 'react'
import { ArrowRight, BookOpen, CheckCircle2, ChevronRight, CircleAlert, Dna, FileSearch, Info, Layers, Plus, RefreshCw, Save, Search, Settings2, ShieldCheck } from 'lucide-react'
import ClinicalLayout from '../../components/layout/ClinicalLayout.jsx'
import { errorMessage } from '../../services/api.js'
import { listPathologies, savePathology } from './api.js'
import SymptomPicker from './SymptomPicker.jsx'
import SuspicionChecker from './SuspicionChecker.jsx'
import './catalog.css'

const emptyForm = () => ({ name: '', cardinal: [], secondary: [] })

export default function PathologyCatalog({ session }) {
  const canEdit = session.role === 'medical_manager'
  const [items, setItems] = useState([])
  const [selected, setSelected] = useState(null)
  const [form, setForm] = useState(emptyForm)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [reload, setReload] = useState(0)
  const [search, setSearch] = useState('')

  useEffect(() => {
    let active = true
    listPathologies().then((data) => {
      if (active) setItems(data)
    }).catch((failure) => {
      if (active) setError(errorMessage(failure))
    }).finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [reload])

  function choose(item) {
    setSelected(item)
    setForm(item ? { name: item.name, cardinal: [item.cardinal_symptom], secondary: item.secondary_symptoms } : emptyForm())
    setError(''); setNotice('')
  }

  async function save(event) {
    event.preventDefault()
    setBusy(true); setError(''); setNotice('')
    try {
      const result = await savePathology(selected?.id, {
        name: form.name.trim(), cardinal_symptom_id: form.cardinal[0].id,
        secondary_symptom_ids: form.secondary.map((term) => term.id),
      })
      setItems((current) => [...current.filter((item) => item.id !== result.id), result]
        .sort((a, b) => a.name.localeCompare(b.name, 'es')))
      choose(result)
      setSearch('')
      setNotice('Patología guardada correctamente.')
    } catch (failure) { setError(errorMessage(failure)) }
    finally { setBusy(false) }
  }

  const filtered = items.filter((item) => item.name.toLocaleLowerCase('es').includes(search.trim().toLocaleLowerCase('es')))
  const checkerKey = selected && `${selected.id}-${selected.cardinal_symptom.id}-${selected.secondary_symptoms.map((s) => s.id).join(',')}-${selected.name}`

  return <ClinicalLayout session={session}><section className="catalog-page">
    <header className="catalog-header">
      <div><p className="catalog-eyebrow">{canEdit ? 'CONFIGURACIÓN DEL DOMINIO CLÍNICO' : 'HERRAMIENTAS DE CONSULTA MÉDICA'}</p>
        <h1>{canEdit ? 'Catálogo de patologías' : 'Validación de sospecha clínica'}</h1>
        <p>{canEdit ? 'Administrá las patologías y los criterios que permiten validar una sospecha médica.' : 'Consultá los criterios de cada patología y contrastalos con los síntomas observados.'}</p>
      </div>
      <div className="catalog-header-actions">
        <button type="button" className="catalog-secondary" disabled={busy || loading} onClick={() => { choose(null); setLoading(true); setReload((v) => v + 1) }}><RefreshCw size={15} aria-hidden="true" />Actualizar catálogo</button>
        {canEdit && <button type="button" className="catalog-primary" disabled={busy || loading} onClick={() => choose(null)}><Plus size={16} aria-hidden="true" />Nueva patología</button>}
      </div>
    </header>

    <div className="catalog-summary" aria-label="Criterios del catálogo">
      <div><span className="catalog-summary-icon"><BookOpen size={20} aria-hidden="true" /></span><span><strong>{loading ? '—' : items.length}</strong><small>Patologías registradas</small></span></div>
      <div><span className="catalog-summary-icon"><ShieldCheck size={20} aria-hidden="true" /></span><span><strong>Síntoma cardinal</strong><small>Permite validar por sí solo</small></span></div>
      <div><span className="catalog-summary-icon"><Layers size={20} aria-hidden="true" /></span><span><strong>2 secundarios distintos</strong><small>Alternativa cuando no hay cardinal</small></span></div>
    </div>

    <aside className="catalog-demo-note"><Info size={17} aria-hidden="true" /><p><strong>Entorno de demostración.</strong> Los conceptos DEMO son ficticios y no corresponden a SNOMED. No uses datos de pacientes reales.</p></aside>

    {loading ? <div role="status" className="catalog-loading"><RefreshCw size={21} aria-hidden="true" /><span>Cargando catálogo...</span></div> : <div className="catalog-layout">
      <nav className="catalog-card catalog-sidebar" aria-label="Patologías">
        <div className="catalog-card-heading"><h2>Patologías disponibles</h2><span className="catalog-count">{items.length}</span></div>
        <label htmlFor="catalog-search" className="catalog-search-label">Buscar patología</label>
        <div className="catalog-search"><Search size={16} aria-hidden="true" /><input id="catalog-search" type="search" value={search} placeholder="Nombre de la patología" onChange={(event) => setSearch(event.target.value)} /></div>
        {items.length === 0 ? <div className="catalog-list-empty"><BookOpen size={26} aria-hidden="true" /><p>Todavía no hay patologías registradas.</p>{canEdit && <small>Completá el formulario para agregar la primera.</small>}</div>
          : filtered.length === 0 ? <p className="catalog-muted catalog-list-empty">No se encontraron patologías con esa búsqueda.</p>
            : <ul className="catalog-pathology-list">{filtered.map((item) => <li key={item.id}><button type="button" disabled={busy} aria-label={item.name}
              className={selected?.id === item.id ? 'catalog-selected' : ''} aria-current={selected?.id === item.id ? 'true' : undefined} onClick={() => choose(item)}>
              <span><strong>{item.name}</strong><small>1 cardinal · {item.secondary_symptoms.length} secundarios</small></span><ChevronRight size={17} aria-hidden="true" />
            </button></li>)}</ul>}
        <div className="catalog-sidebar-note"><ShieldCheck size={15} aria-hidden="true" /><span>{canEdit ? 'Los cambios se aplican a futuras validaciones.' : 'Consulta disponible para el médico tratante.'}</span></div>
      </nav>

      <div className="catalog-content">
        {error && <p role="alert" className="catalog-error"><CircleAlert size={17} aria-hidden="true" />{error}</p>}
        {notice && <p role="status" className="catalog-success"><CheckCircle2 size={17} aria-hidden="true" />{notice}</p>}
        {canEdit ? <section className="catalog-card catalog-editor" aria-labelledby="edit-heading">
          <div className="catalog-section-heading"><span className="catalog-section-icon"><Settings2 size={20} aria-hidden="true" /></span><div><h2 id="edit-heading">{selected ? 'Editar patología' : 'Nueva patología'}</h2><p>Definí los conceptos clínicos asociados a esta patología.</p></div></div>
          <form onSubmit={save}><fieldset disabled={busy} className="catalog-fieldset">
            <div className="catalog-form-section"><span className="catalog-step">01</span><div><h3>Identificación de la patología</h3><p className="catalog-muted">Usá un nombre que permita identificarla en el catálogo.</p></div></div>
            <label htmlFor="pathology-name">Nombre de la patología <span aria-hidden="true">*</span></label>
            <input id="pathology-name" value={form.name} maxLength={160} required placeholder="Ingresá el nombre de la patología" onChange={(event) => setForm({ ...form, name: event.target.value })} />
            <div className="catalog-form-section"><span className="catalog-step">02</span><div><h3>Criterios de validación</h3><p className="catalog-muted">Seleccioná conceptos del catálogo de terminología.</p></div></div>
            <SymptomPicker label="Síntoma cardinal" selected={form.cardinal} onChange={(terms) => setForm({ ...form, cardinal: terms, secondary: form.secondary.filter((s) => s.id !== terms[0]?.id) })} />
            <SymptomPicker label="Síntomas secundarios" multiple selected={form.secondary} excludeIds={form.cardinal.map((s) => s.id)} onChange={(terms) => setForm({ ...form, secondary: terms })} />
            <div className="catalog-rule-note"><Info size={16} aria-hidden="true" /><p>El cardinal es obligatorio y no puede repetirse como secundario. Una patología puede guardarse sin síntomas secundarios.</p></div>
            <div className="catalog-form-footer"><span>* Campo obligatorio</span><button className="catalog-primary" disabled={busy || !form.name.trim() || form.cardinal.length === 0}><Save size={16} aria-hidden="true" />{busy ? 'Guardando...' : 'Guardar patología'}</button></div>
          </fieldset></form>
        </section> : selected ? <section className="catalog-card" aria-labelledby="selected-pathology-heading">
          <div className="catalog-section-heading"><span className="catalog-section-icon"><Dna size={20} aria-hidden="true" /></span><div><span className="catalog-eyebrow">CRITERIOS DE LA PATOLOGÍA</span><h2 id="selected-pathology-heading">{selected.name}</h2></div></div>
          <div className="catalog-cardinal"><span className="catalog-label"><ShieldCheck size={15} aria-hidden="true" />Síntoma cardinal</span><strong>{selected.cardinal_symptom.label}</strong><small>{selected.cardinal_symptom.code_system}: {selected.cardinal_symptom.code}</small></div>
          <h3 className="catalog-secondary-heading">Síntomas secundarios <span className="catalog-count">{selected.secondary_symptoms.length}</span></h3>
          {selected.secondary_symptoms.length ? <ul className="catalog-criteria-list">{selected.secondary_symptoms.map((term) => <li key={term.id}><span className="catalog-criteria-dot" aria-hidden="true" /><span><strong>{term.label}</strong><small>{term.code_system}: {term.code}</small></span></li>)}</ul> : <p className="catalog-muted">No tiene secundarios configurados.</p>}
        </section> : <section className="catalog-card catalog-welcome"><span className="catalog-welcome-icon"><FileSearch size={36} aria-hidden="true" /></span><span className="catalog-eyebrow">CONSULTA DEL CATÁLOGO</span><h2>Comenzá seleccionando una patología</h2><p>Revisá su síntoma cardinal y sus síntomas secundarios. Después podés comprobar la coherencia de una sospecha clínica.</p><span className="catalog-welcome-hint"><ArrowRight size={15} aria-hidden="true" />Elegí una patología del listado</span></section>}
        {selected && <SuspicionChecker key={checkerKey} pathology={selected} />}
      </div>
    </div>}
  </section></ClinicalLayout>
}
