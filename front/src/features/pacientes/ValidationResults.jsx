import { CheckCircle2, CircleAlert } from 'lucide-react'

const messages = {
  cardinal: 'Cumple por el síntoma cardinal.',
  two_secondary: 'Cumple por al menos dos secundarios distintos.',
  insufficient_symptoms: 'No cumple: requiere el cardinal o al menos dos secundarios asociados.',
  family_history: 'Sospecha familiar respaldada por el antecedente documentado.',
}

export default function ValidationResults({ results }) {
  if (!results?.length) return null
  return <div className="patient-validation" aria-label="Resultados por sospecha">
    {results.map((result) => <div key={result.pathology_id} className={result.valid ? 'patient-validation-valid' : 'patient-validation-invalid'}>
      {result.valid ? <CheckCircle2 size={19} aria-hidden="true" /> : <CircleAlert size={19} aria-hidden="true" />}
      <span><strong>{result.name}</strong><small>{messages[result.criterion] ?? result.criterion}</small></span>
    </div>)}
  </div>
}
