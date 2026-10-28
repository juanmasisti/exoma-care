import { useEffect, useState } from 'react'
import { errorMessage } from '../../services/api.js'
import { setSession } from '../../services/session.js'
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
      setNotice('Patología guardada correctamente.')
    } catch (failure) { setError(errorMessage(failure)) }
    finally { setBusy(false) }
  }

  const checkerKey = selected && `${selected.id}-${selected.cardinal_symptom.id}-${selected.secondary_symptoms.map((s) => s.id).join(',')}-${selected.name}`

  return <main className="catalog-page">
    <header className="catalog-header">
      <div><span className="catalog-brand">EXOMA CARE</span><h1>Catálogo de patologías</h1>
        <p>{canEdit ? 'Configurá los criterios de validación de las sospechas clínicas.' : 'Consultá patologías y comprobá la coherencia de una sospecha clínica.'}</p></div>
      <div className="catalog-account"><span>{session.rol}</span><button type="button" onClick={() => setSession(null)}>Cerrar sesión</button></div>
    </header>
    <aside className="catalog-demo-note"><strong>Etapa de demostración.</strong> Los conceptos con código DEMO son ficticios y no corresponden a SNOMED. No uses datos de pacientes reales.</aside>
    {loading ? <p role="status">Cargando catálogo...</p> : <div className="catalog-layout">
      <nav className="catalog-card catalog-sidebar" aria-label="Patologías">
        <h2>Patologías <span className="catalog-count">{items.length}</span></h2>
        {canEdit && <button type="button" className="catalog-primary" disabled={busy} onClick={() => choose(null)}>Nueva patología</button>}
        {items.length === 0 && <p className="catalog-muted">Todavía no hay patologías registradas.</p>}
        <ul>{items.map((item) => <li key={item.id}><button type="button" disabled={busy}
          className={selected?.id === item.id ? 'catalog-selected' : ''} aria-current={selected?.id === item.id ? 'true' : undefined}
          onClick={() => choose(item)}>{item.name}</button></li>)}</ul>
        <button type="button" className="catalog-text-button" disabled={busy} onClick={() => { choose(null); setLoading(true); setReload((v) => v + 1) }}>Actualizar catálogo</button>
      </nav>
      <div className="catalog-content">
        {error && <p role="alert" className="catalog-error">{error}</p>}
        {notice && <p role="status" className="catalog-success">{notice}</p>}
        {canEdit ? <section className="catalog-card" aria-labelledby="edit-heading">
          <h2 id="edit-heading">{selected ? 'Editar patología' : 'Nueva patología'}</h2>
          <form onSubmit={save}><fieldset disabled={busy} className="catalog-fieldset">
            <label htmlFor="pathology-name">Nombre de la patología <span aria-hidden="true">*</span></label>
            <input id="pathology-name" value={form.name} maxLength={160} required
              onChange={(event) => setForm({ ...form, name: event.target.value })} />
            <SymptomPicker label="Síntoma cardinal" selected={form.cardinal} onChange={(terms) => setForm({
              ...form, cardinal: terms, secondary: form.secondary.filter((s) => s.id !== terms[0]?.id),
            })} />
            <SymptomPicker label="Síntomas secundarios" multiple selected={form.secondary}
              excludeIds={form.cardinal.map((s) => s.id)} onChange={(terms) => setForm({ ...form, secondary: terms })} />
            <p className="catalog-muted">El síntoma cardinal es obligatorio y no puede repetirse como secundario. Se puede guardar una patología sin secundarios.</p>
            <button className="catalog-primary" disabled={busy || !form.name.trim() || form.cardinal.length === 0}>{busy ? 'Guardando...' : 'Guardar patología'}</button>
          </fieldset></form>
        </section> : selected ? <section className="catalog-card">
          <h2>{selected.name}</h2><h3>Síntoma cardinal</h3><p>{selected.cardinal_symptom.label} <small>({selected.cardinal_symptom.code_system}: {selected.cardinal_symptom.code})</small></p>
          <h3>Síntomas secundarios</h3>{selected.secondary_symptoms.length ? <ul>{selected.secondary_symptoms.map((term) => <li key={term.id}>{term.label} ({term.code_system}: {term.code})</li>)}</ul> : <p>No tiene secundarios configurados.</p>}
        </section> : <section className="catalog-card"><h2>Consulta del catálogo</h2><p>Seleccioná una patología para ver sus criterios y validar una sospecha clínica.</p></section>}
        {selected && <SuspicionChecker key={checkerKey} pathology={selected} />}
      </div>
    </div>}
  </main>
}
