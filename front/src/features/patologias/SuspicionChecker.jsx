import { useState } from 'react'
import { ArrowRight, CheckCircle2, CircleAlert, Info, ShieldCheck, Stethoscope } from 'lucide-react'
import { errorMessage } from '../../services/api.js'
import { validateSuspicion } from './api.js'
import SymptomPicker from './SymptomPicker.jsx'

const criteria = {
  cardinal: 'Presenta el síntoma cardinal de la patología.',
  two_secondary: 'Presenta al menos dos síntomas secundarios distintos de la patología.',
  insufficient_symptoms: 'No presenta el cardinal ni al menos dos síntomas secundarios de esta patología.',
}

export default function SuspicionChecker({ pathology }) {
  const [selected, setSelected] = useState([])
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  async function check(event) {
    event.preventDefault()
    setBusy(true); setResult(null); setError('')
    try {
      setResult(await validateSuspicion(pathology.id, selected.map((term) => term.id)))
    } catch (failure) { setError(errorMessage(failure)) }
    finally { setBusy(false) }
  }

  return <section className="catalog-card catalog-checker" aria-labelledby="validation-heading">
    <div className="catalog-section-heading"><span className="catalog-section-icon"><Stethoscope size={20} aria-hidden="true" /></span><div><span className="catalog-eyebrow">COMPROBACIÓN INDIVIDUAL</span><h2 id="validation-heading">Validar sospecha clínica</h2></div></div>
    <div className="catalog-checker-context"><ShieldCheck size={17} aria-hidden="true" /><span>Patología bajo sospecha<strong>{pathology.name}</strong></span></div>
    <form onSubmit={check}>
      <fieldset disabled={busy} className="catalog-fieldset">
        <SymptomPicker label="Síntomas presentes" multiple selected={selected} onChange={(terms) => { setSelected(terms); setResult(null); setError('') }} />
        <div className="catalog-checker-actions"><span>{selected.length} {selected.length === 1 ? 'síntoma seleccionado' : 'síntomas seleccionados'}</span><button className="catalog-primary" disabled={busy}>{busy ? 'Validando...' : 'Validar sospecha'}<ArrowRight size={16} aria-hidden="true" /></button></div>
      </fieldset>
    </form>
    {error && <p role="alert" className="catalog-error"><CircleAlert size={17} aria-hidden="true" />{error}</p>}
    {result && <div role="status" className={`validation-result ${result.valid ? 'is-valid' : 'is-invalid'}`}>
      {result.valid ? <CheckCircle2 size={23} aria-hidden="true" /> : <CircleAlert size={23} aria-hidden="true" />}
      <div><strong>{result.valid ? 'Sospecha consistente' : 'Criterio no cumplido'}</strong><p>{criteria[result.criterion]}</p><span>Secundarios coincidentes: {result.matched_secondary_ids.length}</span></div>
    </div>}
    <p className="catalog-clinical-disclaimer"><Info size={15} aria-hidden="true" /><span>No establece un diagnóstico ni confirma el alta de un paciente. La comprobación evalúa la coherencia de esta sospecha con los síntomas seleccionados.</span></p>
  </section>
}
