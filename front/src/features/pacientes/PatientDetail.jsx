import { useEffect, useState } from 'react'
import { ArrowLeft, Clock, Edit3, FileText, Mail, Phone, ShieldCheck, User } from 'lucide-react'
import { Link, useLocation, useParams } from 'react-router-dom'
import ClinicalLayout from '../../components/layout/ClinicalLayout.jsx'
import { errorMessage } from '../../services/api.js'
import { getPatient, getPatientHistory } from './api.js'
import ValidationResults from './ValidationResults.jsx'
import './patients.css'

function dateLabel(value) { return value ? new Date(`${value.slice(0, 10)}T12:00:00`).toLocaleDateString('es-AR') : 'Sin registrar' }

export default function PatientDetail({ session }) {
  const { patientId } = useParams()
  const location = useLocation()
  const [patient, setPatient] = useState(null)
  const [history, setHistory] = useState([])
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const [tab, setTab] = useState('clinical')

  useEffect(() => {
    let active = true
    Promise.all([getPatient(patientId), getPatientHistory(patientId)]).then(([record, revisions]) => {
      if (active) { setPatient(record); setHistory(revisions) }
    }).catch((failure) => { if (active) setError(errorMessage(failure)) })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [patientId])

  return <ClinicalLayout session={session} pageLabel="Ficha del paciente"><section className="patients-page">
    <Link to="/medico/pacientes" className="patient-back"><ArrowLeft size={15} aria-hidden="true" />Volver a pacientes</Link>
    {location.state?.notice && <p role="status" className="patient-success">{location.state.notice}</p>}
    {loading ? <p role="status">Cargando ficha...</p> : error ? <p role="alert" className="patient-error">{error}</p> : patient && <>
      <section className="patient-card patient-profile-header"><div className="patient-profile-name"><span className="patient-avatar patient-avatar-large" aria-hidden="true">{patient.first_name[0]}{patient.last_name[0]}</span><div><span className="patients-eyebrow">FICHA DEL PACIENTE</span><h1>{patient.last_name}, {patient.first_name}</h1><p>DNI {patient.dni} · Nacimiento: {dateLabel(patient.birth_date)}</p></div></div><Link to={`/medico/pacientes/${patient.id}/editar`} className="patient-primary"><Edit3 size={16} aria-hidden="true" />Editar paciente</Link></section>
      <div className="patient-contact-grid"><div><Phone size={16} aria-hidden="true" /><span><small>Teléfono</small>{patient.phone || 'Sin registrar'}</span></div><div><Mail size={16} aria-hidden="true" /><span><small>Email de contacto</small>{patient.email || 'Sin registrar'}</span></div><div><ShieldCheck size={16} aria-hidden="true" /><span><small>Acceso a la plataforma</small>{patient.access_status === 'pending' ? 'Pendiente de habilitación' : 'Cuenta vinculada'}</span></div></div>
      <div className="patient-tabs" role="tablist" aria-label="Información del paciente"><button type="button" id="tab-clinical" role="tab" aria-selected={tab === 'clinical'} aria-controls="patient-clinical-panel" onClick={() => setTab('clinical')}><FileText size={16} aria-hidden="true" />Información clínica</button><button type="button" id="tab-history" role="tab" aria-selected={tab === 'history'} aria-controls="patient-history-panel" onClick={() => setTab('history')}><Clock size={16} aria-hidden="true" />Historial de cambios ({history.length})</button></div>
      {tab === 'clinical' ? <section id="patient-clinical-panel" role="tabpanel" aria-labelledby="tab-clinical" className="patient-detail-grid">
        <div className="patient-card"><div className="patient-section-heading"><User size={19} aria-hidden="true" /><h2>Sospecha e información clínica</h2></div><span className="patient-type">{patient.suspicion_type === 'family' ? 'Sospecha familiar' : patient.suspicion_type === 'clinical' ? 'Sospecha clínica' : 'Por completar'}</span><h3>Resumen de historia clínica</h3><p className="patient-preserve-text">{patient.clinical_summary || 'Información clínica por completar.'}</p>{patient.family_history && <><h3>Antecedente familiar documentado</h3><p className="patient-preserve-text">{patient.family_history}</p></>}<h3>Síntomas registrados ({patient.symptoms.length})</h3>{patient.symptoms.length ? <ul className="patient-saved-symptoms">{patient.symptoms.map((term) => <li key={term.id}><strong>{term.label}</strong><small>{term.code_system}: {term.code}</small></li>)}</ul> : <p className="patient-help">No hay síntomas registrados.</p>}</div>
        <div className="patient-card"><h2>Evidencia de validación</h2><p className="patient-help">Versión {patient.version}. Se conservan los criterios utilizados al guardar, aunque después se modifique el catálogo.</p><ValidationResults results={patient.suspicions} /><p className="patient-help">Los conceptos DEMO provienen del prototipo y no constituyen terminología clínica validada. El alta no genera un estudio.</p></div>
      </section> : <section id="patient-history-panel" role="tabpanel" aria-labelledby="tab-history" className="patient-card"><h2>Historial de información clínica</h2><p className="patient-help">Cada guardado conserva la información y su evidencia anterior.</p>{history.length === 0 ? <p>No hay revisiones clínicas registradas.</p> : history.map((revision) => <details key={revision.version} className="patient-revision"><summary>Versión {revision.version} · {dateLabel(revision.changed_at)}</summary><p className="patient-help">Profesional: {revision.changed_by_name || 'Médico tratante'}</p><p className="patient-preserve-text">{revision.snapshot.patient_data.clinical_summary}</p><ValidationResults results={revision.snapshot.suspicions} /></details>)}</section>}
    </>}
  </section></ClinicalLayout>
}
