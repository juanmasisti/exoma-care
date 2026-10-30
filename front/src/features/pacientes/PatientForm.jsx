import { useEffect, useRef, useState } from 'react'
import { ArrowLeft, CheckCircle2, FileText, Info, Save, User } from 'lucide-react'
import { useNavigate, useParams } from 'react-router-dom'
import ClinicalLayout from '../../components/layout/ClinicalLayout.jsx'
import { errorMessage } from '../../services/api.js'
import { listPathologies } from '../patologias/api.js'
import SymptomPicker from '../patologias/SymptomPicker.jsx'
import { evaluatePatient, getPatient, savePatient } from './api.js'
import ValidationResults from './ValidationResults.jsx'
import './patients.css'

const blank = () => ({ dni: '', first_name: '', last_name: '', birth_date: '', phone: '', email: '', clinical_summary: '', suspicion_type: 'clinical', family_history: '', pathology_ids: [], symptoms: [] })
const localDate = () => { const d = new Date(); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}` }

export default function PatientForm({ session }) {
  const { patientId } = useParams()
  const navigate = useNavigate()
  const [form, setForm] = useState(blank)
  const [version, setVersion] = useState(null)
  const [catalog, setCatalog] = useState([])
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [evaluation, setEvaluation] = useState(null)
  const alive = useRef(true)

  useEffect(() => {
    alive.current = true
    let active = true
    Promise.all([listPathologies(), patientId ? getPatient(patientId) : null]).then(([pathologies, patient]) => {
      if (!active) return
      setCatalog(pathologies)
      if (patient) {
        const values = blank()
        for (const key of Object.keys(values)) if (patient[key] != null) values[key] = patient[key]
        setForm(values); setVersion(patient.version)
      }
    }).catch((failure) => { if (active) setError(errorMessage(failure)) })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false; alive.current = false }
  }, [patientId])

  function change(key, value) { setForm((previous) => ({ ...previous, [key]: value })); setEvaluation(null); setError('') }
  function toggle(id) { change('pathology_ids', form.pathology_ids.includes(id) ? form.pathology_ids.filter((value) => value !== id) : [...form.pathology_ids, id]) }
  function body() { const { symptoms, ...values } = form; return { ...values, symptom_ids: symptoms.map((term) => term.id) } }

  async function submit(event) {
    event.preventDefault()
    if (!form.pathology_ids.length) { setError('Seleccioná al menos una patología sospechada.'); return }
    const action = event.nativeEvent.submitter?.value ?? 'save'
    setBusy(true); setError(''); setEvaluation(null)
    try {
      if (action === 'validate') {
        const result = await evaluatePatient(body())
        if (alive.current) setEvaluation(result)
      } else {
        const result = await savePatient(patientId, patientId ? { ...body(), version } : body())
        if (alive.current) navigate(`/medico/pacientes/${result.id}`, { state: { notice: patientId ? 'Información del paciente actualizada.' : 'Paciente registrado. El alta no creó un estudio y su acceso está pendiente de habilitación.' } })
      }
    } catch (failure) {
      if (!alive.current) return
      setError(errorMessage(failure))
      const results = failure.response?.data?.detail?.results
      if (results) setEvaluation({ valid: false, results })
    } finally { if (alive.current) setBusy(false) }
  }

  const heading = patientId ? 'Editar paciente' : 'Alta de paciente'
  return <ClinicalLayout session={session} pageLabel={heading}><section className="patients-page patient-form-page">
    <button type="button" className="patient-back" disabled={busy} onClick={() => navigate(patientId ? `/medico/pacientes/${patientId}` : '/medico/pacientes')}><ArrowLeft size={15} aria-hidden="true" />Volver</button>
    <header className="patients-header"><div><span className="patients-eyebrow">INFORMACIÓN CLÍNICA</span><h1>{heading}</h1><p>Registrá los datos personales y validá las sospechas antes de guardar. Esta operación no genera un estudio.</p></div></header>
    <aside className="patient-demo-note"><Info size={17} aria-hidden="true" /><span>Datos de demostración: las asociaciones de síntomas de las cinco patologías provienen del prototipo y usan códigos DEMO, no SNOMED.</span></aside>
    {error && <div role="alert" className="patient-error">{error}</div>}
    {loading ? <p role="status">Cargando formulario...</p> : <form onSubmit={submit}><fieldset disabled={busy} className="patient-form-fieldset">
      <section className="patient-card"><div className="patient-section-heading"><User size={20} aria-hidden="true" /><h2>1. Información personal y de contacto</h2></div>
        <div className="patient-fields-grid">
          {[['dni', 'DNI', 'text', 30], ['first_name', 'Nombre', 'text', 100], ['last_name', 'Apellido', 'text', 100], ['birth_date', 'Fecha de nacimiento', 'date'], ['phone', 'Teléfono', 'tel', 30], ['email', 'Email de contacto', 'email', 255]].map(([key, label, type, maxLength]) => <div key={key}><label htmlFor={`patient-${key}`}>{label} <span aria-hidden="true">*</span></label><input id={`patient-${key}`} type={type} value={form[key]} maxLength={maxLength} max={type === 'date' ? localDate() : undefined} required onChange={(event) => change(key, event.target.value)} /></div>)}
        </div>
      </section>
      <section className="patient-card"><div className="patient-section-heading"><FileText size={20} aria-hidden="true" /><h2>2. Sospecha médica e historia clínica</h2></div>
        <label htmlFor="patient-suspicion">Tipo de sospecha <span aria-hidden="true">*</span></label><select id="patient-suspicion" value={form.suspicion_type} onChange={(event) => change('suspicion_type', event.target.value)}><option value="clinical">Clínica</option><option value="family">Familiar</option></select>
        <div className="patient-field-space"><label htmlFor="patient-summary">Resumen de historia clínica <span aria-hidden="true">*</span></label><textarea id="patient-summary" rows={5} value={form.clinical_summary} maxLength={20000} required onChange={(event) => change('clinical_summary', event.target.value)} /></div>
        {form.suspicion_type === 'family' && <div className="patient-field-space"><label htmlFor="patient-family">Antecedente familiar documentado <span aria-hidden="true">*</span></label><textarea id="patient-family" rows={3} maxLength={10000} value={form.family_history} required onChange={(event) => change('family_history', event.target.value)} /><p className="patient-help">Documentá el antecedente que respalda la sospecha. En este caso no se exige que el paciente presente síntomas.</p></div>}
        <fieldset className="patient-pathology-fieldset"><legend>Patologías sospechadas <span aria-hidden="true">*</span></legend><p className="patient-help">Podés seleccionar varias. Si la sospecha es clínica, todas deben cumplir el criterio antes de guardar.</p>
          {catalog.length === 0 && <p className="patient-error">No hay patologías disponibles. El gerente debe configurar el catálogo antes del alta.</p>}
          <div className="patient-pathology-options">{catalog.map((pathology) => <label key={pathology.id} className={form.pathology_ids.includes(pathology.id) ? 'patient-pathology-selected' : ''}><input type="checkbox" checked={form.pathology_ids.includes(pathology.id)} onChange={() => toggle(pathology.id)} /><span>{pathology.name}</span></label>)}</div>
        </fieldset>
        {catalog.filter((pathology) => form.pathology_ids.includes(pathology.id)).map((pathology) => <details key={pathology.id} className="patient-pathology-criteria"><summary>Criterios de {pathology.name}</summary><p><strong>Cardinal:</strong> {pathology.cardinal_symptom.label}</p><p><strong>Secundarios:</strong> {pathology.secondary_symptoms.map((term) => term.label).join(' · ') || 'Sin secundarios configurados.'}</p></details>)}
        <div className="patient-symptom-picker"><SymptomPicker label="Síntomas presentes" multiple selected={form.symptoms} onChange={(terms) => change('symptoms', terms)} /></div>
        {evaluation && <div role="status"><p className={evaluation.valid ? 'patient-success' : 'patient-error'}><CheckCircle2 size={17} aria-hidden="true" />{evaluation.valid ? 'Las sospechas cumplen los criterios para guardar.' : 'Revisá las sospechas que no cumplen los criterios.'}</p><ValidationResults results={evaluation.results} /></div>}
        <p className="patient-help">La comprobación valida la coherencia de las sospechas. No establece un diagnóstico.</p>
      </section>
      <div className="patient-form-actions"><span>* Campos obligatorios. El acceso del paciente se habilita por separado.</span><div><button type="submit" value="validate" className="patient-secondary" disabled={busy || !catalog.length}>Validar sospechas</button><button type="submit" value="save" className="patient-primary" disabled={busy || !catalog.length}><Save size={16} aria-hidden="true" />{busy ? 'Procesando...' : patientId ? 'Guardar cambios' : 'Guardar paciente'}</button></div></div>
    </fieldset></form>}
  </section></ClinicalLayout>
}
