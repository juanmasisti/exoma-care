import { useState } from 'react'
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
    } catch (failure) {
      setError(errorMessage(failure))
    } finally { setBusy(false) }
  }

  return <section className="catalog-card" aria-labelledby="validation-heading">
    <h2 id="validation-heading">Validar sospecha clínica</h2>
    <p className="catalog-muted">Comprobación individual para <strong>{pathology.name}</strong>. No establece un diagnóstico ni confirma el alta de un paciente.</p>
    <form onSubmit={check}>
      <fieldset disabled={busy} className="catalog-fieldset">
        <SymptomPicker label="Síntomas presentes" multiple selected={selected} onChange={(terms) => {
          setSelected(terms); setResult(null); setError('')
        }} />
        <button className="catalog-primary" disabled={busy}>{busy ? 'Validando...' : 'Validar sospecha'}</button>
      </fieldset>
    </form>
    {error && <p role="alert" className="catalog-error">{error}</p>}
    {result && <div role="status" className={`validation-result ${result.valid ? 'is-valid' : 'is-invalid'}`}>
      <strong>{result.valid ? 'Sospecha consistente' : 'Criterio no cumplido'}</strong>
      <p>{criteria[result.criterion]}</p>
      <span>Secundarios coincidentes: {result.matched_secondary_ids.length}</span>
    </div>}
  </section>
}
