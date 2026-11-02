import { useEffect, useRef, useState } from 'react'
import { Clock, Edit3, Info, Plus, Save, Users } from 'lucide-react'
import { errorMessage } from '../../services/api.js'
import { listPathologies } from '../patologias/api.js'
import SymptomPicker from '../patologias/SymptomPicker.jsx'
import { getFamily, getFamilyHistory, saveFamily } from './familyApi.js'
import './family.css'

const relationships = { mother: 'Madre', father: 'Padre', sibling: 'Hermano/a', child: 'Hijo/a', aunt_uncle: 'Tío/a', grandparent: 'Abuelo/a', cousin: 'Primo/a', other: 'Otro parentesco' }
const diagnosisLabels = { unknown: 'Sin información diagnóstica', none: 'Sin diagnóstico conocido', known: 'Diagnóstico conocido' }
const blankMember = () => ({ full_name: '', relationship: '', relationship_detail: '', symptom_ids: [], diagnosis_status: 'unknown', diagnosis_ids: [], symptoms: [], diagnoses: [], notes: '' })
const toRequest = (member) => Object.fromEntries(['full_name', 'relationship', 'relationship_detail', 'symptom_ids', 'diagnosis_status', 'diagnosis_ids', 'notes'].map(key => [key, member[key]]))

function FamilyMemberSummary({ member }) {
  return <><div className="family-member-heading"><strong>{member.full_name}</strong><span className="patient-type">{relationships[member.relationship] || member.relationship}</span></div>
    {member.relationship_detail && <p className="patient-help">{member.relationship_detail}</p>}
    <p className="family-diagnosis"><strong>{diagnosisLabels[member.diagnosis_status]}</strong>{member.diagnoses.length > 0 && `: ${member.diagnoses.map(d => d.name).join(' · ')}`}</p>
    <p className="patient-help">Síntomas: {member.symptoms.length ? member.symptoms.map(s => `${s.label} (${s.code_system}: ${s.code})`).join(' · ') : 'Sin síntomas registrados.'}</p>
    {member.notes && <p className="patient-preserve-text">{member.notes}</p>}
  </>
}

function MemberEditor({ initial, catalog, editing, onConfirm, onCancel }) {
  const [form, setForm] = useState(initial)
  const [error, setError] = useState('')
  function change(key, value) { setForm(previous => ({ ...previous, [key]: value })); setError('') }
  function submit(event) {
    event.preventDefault()
    if (!form.full_name.trim() || !form.relationship) { setError('Completá el nombre y el parentesco.'); return }
    if (form.relationship === 'other' && !form.relationship_detail.trim()) { setError('Aclará el parentesco al seleccionar Otro.'); return }
    if (form.diagnosis_status === 'known' && !form.diagnosis_ids.length) { setError('Seleccioná al menos una patología para el diagnóstico conocido.'); return }
    onConfirm({ ...form, full_name: form.full_name.trim(), diagnoses: catalog.filter(p => form.diagnosis_ids.includes(p.id)).map(p => ({ id: p.id, name: p.name })) })
  }
  return <form className="family-editor" onSubmit={submit} aria-label="Datos del familiar">
    <h3>{editing ? 'Editar antecedente familiar' : 'Agregar antecedente familiar'}</h3>
    {error && <p role="alert" className="patient-error">{error}</p>}
    <div className="patient-fields-grid"><div><label htmlFor="family-name">Nombre del familiar <span aria-hidden="true">*</span></label><input id="family-name" value={form.full_name} maxLength={200} required onChange={e => change('full_name', e.target.value)} /></div>
      <div><label htmlFor="family-relationship">Parentesco <span aria-hidden="true">*</span></label><select id="family-relationship" value={form.relationship} required onChange={e => change('relationship', e.target.value)}><option value="">Seleccionar parentesco</option>{Object.entries(relationships).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></div>
      {form.relationship === 'other' && <div><label htmlFor="family-relationship-detail">Aclaración del parentesco <span aria-hidden="true">*</span></label><input id="family-relationship-detail" value={form.relationship_detail} maxLength={100} required onChange={e => change('relationship_detail', e.target.value)} /></div>}
    </div>
    <div className="patient-field-space"><SymptomPicker label="Síntomas del familiar" multiple selected={form.symptoms} onChange={symptoms => { setForm(previous => ({ ...previous, symptoms, symptom_ids: symptoms.map(s => s.id) })); setError('') }} /></div>
    <div className="patient-field-space"><label htmlFor="family-diagnosis-status">Información diagnóstica</label><select id="family-diagnosis-status" value={form.diagnosis_status} onChange={e => { setForm(previous => ({ ...previous, diagnosis_status: e.target.value, diagnosis_ids: e.target.value === 'known' ? previous.diagnosis_ids : [], diagnoses: [] })); setError('') }}>{Object.entries(diagnosisLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></div>
    {form.diagnosis_status === 'known' && <fieldset className="patient-pathology-fieldset"><legend>Patologías con diagnóstico conocido</legend><p className="patient-help">Registrá antecedentes informados. Esta sección no diagnostica ni valida una sospecha a partir de síntomas.</p><div className="patient-pathology-options">{catalog.map(p => <label key={p.id}><input type="checkbox" checked={form.diagnosis_ids.includes(p.id)} onChange={() => change('diagnosis_ids', form.diagnosis_ids.includes(p.id) ? form.diagnosis_ids.filter(id => id !== p.id) : [...form.diagnosis_ids, p.id])} /><span>{p.name}</span></label>)}</div>{catalog.length === 0 && <p>No hay patologías disponibles en el catálogo.</p>}</fieldset>}
    <div className="patient-field-space"><label htmlFor="family-notes">Observaciones del familiar</label><textarea id="family-notes" rows={3} value={form.notes} maxLength={4000} onChange={e => change('notes', e.target.value)} /></div>
    <div className="family-actions"><button type="button" onClick={onCancel}>Cancelar familiar</button><button type="submit" className="patient-primary">{editing ? 'Aplicar cambios a la lista' : 'Incorporar a la lista'}</button></div>
  </form>
}

export default function FamilySection({ patientId, active }) {
  const [family, setFamily] = useState(null)
  const [catalog, setCatalog] = useState([])
  const [draft, setDraft] = useState([])
  const [editing, setEditing] = useState(false)
  const [editor, setEditor] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [history, setHistory] = useState(null)
  const [historyOpen, setHistoryOpen] = useState(false)
  const [historyLoading, setHistoryLoading] = useState(false)
  const [remote, setRemote] = useState(null)
  const [conflict, setConflict] = useState(false)
  const [retry, setRetry] = useState(0)
  const alive = useRef(true)
  useEffect(() => { alive.current = true; return () => { alive.current = false } }, [])
  useEffect(() => {
    if (!active || family) return
    let cancelled = false
    Promise.all([getFamily(patientId), listPathologies()]).then(([data, pathologies]) => { if (!cancelled) { setFamily(data); setCatalog(pathologies); setError('') } })
      .catch(failure => { if (!cancelled) setError(errorMessage(failure)) })
    return () => { cancelled = true }
  }, [active, family, patientId, retry])
  useEffect(() => {
    if (!editing) return
    const warn = event => { event.preventDefault(); event.returnValue = '' }
    window.addEventListener('beforeunload', warn)
    return () => window.removeEventListener('beforeunload', warn)
  }, [editing])

  function begin() { setDraft(family.members.map(m => ({ ...m }))); setEditing(true); setNotice(''); setError(''); setConflict(false); setRemote(null) }
  function cancel() { setEditing(false); setEditor(null); setDraft([]); setError(''); setConflict(false); setRemote(null) }
  function confirmMember(member) { setDraft(previous => editor.index == null ? [...previous, member] : previous.map((m, index) => index === editor.index ? member : m)); setEditor(null) }
  async function save() {
    setBusy(true); setError(''); setNotice(''); setConflict(false)
    try {
      const result = await saveFamily(patientId, { version: family.version, members: draft.map(toRequest) })
      if (alive.current) { setFamily(result); setEditing(false); setDraft([]); setHistory(null); setHistoryOpen(false); setRemote(null); setNotice('Información familiar guardada. La ficha clínica y la cuenta del paciente no cambiaron.') }
    } catch (failure) { if (alive.current) { setError(errorMessage(failure)); setConflict(failure.response?.status === 409) } }
    finally { if (alive.current) setBusy(false) }
  }
  async function showHistory() {
    if (historyOpen) { setHistoryOpen(false); return }
    setHistoryLoading(true); setError('')
    try { const result = await getFamilyHistory(patientId); if (alive.current) { setHistory(result); setHistoryOpen(true) } }
    catch (failure) { if (alive.current) setError(errorMessage(failure)) }
    finally { if (alive.current) setHistoryLoading(false) }
  }
  async function compare() {
    setBusy(true)
    try { const current = await getFamily(patientId); if (alive.current) setRemote(current) }
    catch (failure) { if (alive.current) setError(errorMessage(failure)) }
    finally { if (alive.current) setBusy(false) }
  }
  if (!active && !family) return null
  return <section id="patient-family-panel" role="tabpanel" aria-labelledby="tab-family" hidden={!active} className="patient-card family-section">
    <header className="family-heading"><div><div className="patient-section-heading"><Users size={20} aria-hidden="true" /><h2>Información familiar</h2></div><p className="patient-help">Antecedentes opcionales referidos por el paciente. Los familiares no reciben una cuenta ni se registran como pacientes.</p></div>{family && !editing && <button type="button" onClick={begin}><Edit3 size={15} aria-hidden="true" />Editar familiares</button>}</header>
    <aside className="patient-demo-note"><Info size={17} aria-hidden="true" /><span>PDF del familiograma pendiente de integración con su API externa. No hay un PDF generado ni una conexión simulada. Los conceptos DEMO conservan su identificación de demostración.</span></aside>
    {notice && <p role="status" className="patient-success">{notice}</p>}
    {error && <p role="alert" className="patient-error">{error}</p>}
    {!family ? error ? <button type="button" onClick={() => { setError(''); setRetry(n => n + 1) }}>Reintentar carga familiar</button> : <p role="status">Cargando información familiar...</p> : <>
      <p className="patient-help">Versión familiar {family.version}. Este historial es independiente de las versiones de información clínica.</p>
      <fieldset className="family-controls" disabled={busy}>
        {(editing ? draft : family.members).length === 0 ? <div className="family-empty"><Users size={28} aria-hidden="true" /><h3>{editing ? 'La lista familiar está vacía' : 'Todavía no hay familiares registrados'}</h3><p className="patient-help">Podés dejar esta sección vacía. No impide el alta ni modifica la validación clínica.</p></div> : <div className="family-members">{(editing ? draft : family.members).map((member, index) => <article className="family-member" key={index}><FamilyMemberSummary member={member} />{editing && !editor && <div className="family-actions"><button type="button" onClick={() => setEditor({ index, data: { ...member } })}>Editar {member.full_name}</button><button type="button" className="family-remove" onClick={() => setDraft(previous => previous.filter((_, i) => i !== index))}>Quitar {member.full_name}</button></div>}</article>)}</div>}
        {editing && <>
          {editor ? <MemberEditor key={editor.index ?? 'new'} initial={editor.data} catalog={catalog} editing={editor.index != null} onConfirm={confirmMember} onCancel={() => setEditor(null)} /> : <button type="button" disabled={draft.length >= 50} onClick={() => setEditor({ index: null, data: blankMember() })}><Plus size={16} aria-hidden="true" />Agregar familiar</button>}
          <p className="patient-help">Los cambios de la lista, incluidas las bajas, se aplican al guardar. Las versiones anteriores se conservan. Máximo 50 familiares por ficha.</p>
          <div className="family-actions"><button type="button" onClick={cancel}>Cancelar edición</button><button type="button" className="patient-primary" disabled={Boolean(editor)} onClick={save}><Save size={15} aria-hidden="true" />{busy ? 'Guardando...' : 'Guardar información familiar'}</button></div>
        </>}
        {conflict && <div className="family-conflict"><p>Tu borrador se conserva. Consultá lo que está guardado para comparar antes de decidir.</p><button type="button" onClick={compare}>Consultar versión actual</button>{remote && <><h3>Versión guardada {remote.version}</h3>{remote.members.length ? remote.members.map((m, i) => <article className="family-member" key={i}><FamilyMemberSummary member={m} /></article>) : <p>No hay familiares en la versión guardada.</p>}<p>Si conservás tu borrador, al guardar reemplazarás la lista mostrada arriba. Revisá e incorporá los cambios del otro profesional que quieras mantener antes de confirmar.</p><div className="family-actions"><button type="button" onClick={() => { setFamily(remote); setRemote(null); setConflict(false); setError(''); setNotice('Borrador conservado sobre la versión consultada. Revisá la lista antes de guardar; los cambios posteriores de otros médicos seguirán generando conflicto.') }}>Continuar con mi borrador sobre la versión actual</button><button type="button" onClick={() => { setFamily(remote); cancel() }}>Usar versión actual y descartar mi borrador</button></div></>}</div>}
      </fieldset>
      <div className="family-history"><button type="button" disabled={busy || historyLoading} onClick={showHistory}><Clock size={15} aria-hidden="true" />{historyLoading ? 'Cargando historial...' : historyOpen ? 'Ocultar historial familiar' : 'Ver historial familiar'}</button>{historyOpen && <div><h3>Historial familiar</h3>{history?.length === 0 ? <p className="patient-help">Todavía no se guardaron revisiones familiares.</p> : history?.map(revision => <details className="patient-revision" key={revision.version}><summary>Versión familiar {revision.version} · {new Date(revision.changed_at).toLocaleDateString('es-AR')}</summary><p className="patient-help">Profesional: {revision.changed_by_name}</p>{revision.members.length ? revision.members.map((member, index) => <article className="family-member" key={index}><FamilyMemberSummary member={member} /></article>) : <p className="patient-help">Se guardó la sección familiar vacía.</p>}</details>)}</div>}</div>
    </>}
  </section>
}
