import { useEffect, useState } from 'react'
import { ArrowLeft, ArrowRight, ChevronRight, Plus, Search, Users } from 'lucide-react'
import { Link } from 'react-router-dom'
import ClinicalLayout from '../../components/layout/ClinicalLayout.jsx'
import { errorMessage } from '../../services/api.js'
import { listPatients } from './api.js'
import './patients.css'

export default function PatientsList({ session }) {
  const [query, setQuery] = useState('')
  const [offset, setOffset] = useState(0)
  const [data, setData] = useState({ items: [], total: 0, limit: 20 })
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [retry, setRetry] = useState(0)

  useEffect(() => {
    const controller = new AbortController()
    const timer = setTimeout(async () => {
      try {
        const result = await listPatients(query, offset, controller.signal)
        if (!controller.signal.aborted) setData(result)
      } catch (failure) {
        if (!controller.signal.aborted) setError(errorMessage(failure))
      } finally { if (!controller.signal.aborted) setLoading(false) }
    }, 250)
    return () => { clearTimeout(timer); controller.abort() }
  }, [query, offset, retry])

  function page(next) { setLoading(true); setError(''); setOffset(next) }

  return <ClinicalLayout session={session}><section className="patients-page">
    <header className="patients-header"><div><span className="patients-eyebrow">GESTIÓN CLÍNICA</span><h1>Pacientes</h1><p>Consultá la información clínica registrada y acompañá cada nueva evaluación.</p></div>
      <Link to="/medico/pacientes/nuevo" className="patient-primary"><Plus size={16} aria-hidden="true" />Nuevo paciente</Link>
    </header>
    <section className="patient-card">
      <div className="patients-list-heading"><div><h2>Pacientes registrados <span className="patient-count">{data.total}</span></h2><p>Listado compartido entre médicos tratantes.</p></div>
        <div className="patients-search"><Search size={17} aria-hidden="true" /><label className="patient-sr-only" htmlFor="patient-search">Buscar pacientes</label><input id="patient-search" type="search" value={query} maxLength={100} placeholder="Buscar por nombre, apellido o DNI" onChange={(event) => { setQuery(event.target.value); setOffset(0); setLoading(true); setError('') }} /></div>
      </div>
      {error ? <div role="alert" className="patient-error"><p>{error}</p><button type="button" onClick={() => { setError(''); setLoading(true); setRetry((n) => n + 1) }}>Reintentar</button></div>
        : loading ? <p role="status" className="patient-loading">Cargando pacientes...</p>
          : data.items.length === 0 ? <div className="patients-empty"><Users size={36} aria-hidden="true" /><h3>{query ? 'No se encontraron pacientes' : 'Todavía no hay pacientes registrados'}</h3><p>{query ? 'Probá con otro nombre o DNI.' : 'Registrá al paciente con sus datos clínicos y sospechas. El alta no crea un estudio.'}</p></div>
            : <div className="patients-table-scroll"><table className="patients-table"><thead><tr><th>Paciente</th><th>DNI</th><th>Sospechas registradas</th><th>Tipo</th><th><span className="patient-sr-only">Acciones</span></th></tr></thead><tbody>
              {data.items.map((patient) => <tr key={patient.id}><td><div className="patient-table-name"><span className="patient-avatar" aria-hidden="true">{patient.first_name[0]}{patient.last_name[0]}</span><span><strong>{patient.last_name}, {patient.first_name}</strong><small>{patient.access_status === 'pending' ? 'Acceso del paciente pendiente' : 'Cuenta vinculada'}</small></span></div></td>
                <td className="patient-dni">{patient.dni}</td><td>{patient.pathology_names.length ? patient.pathology_names.join(' · ') : 'Información clínica por completar'}</td><td><span className="patient-type">{patient.suspicion_type === 'family' ? 'Familiar' : patient.suspicion_type === 'clinical' ? 'Clínica' : 'Por completar'}</span></td><td><Link to={`/medico/pacientes/${patient.id}`} className="patient-detail-link" aria-label={`Ver ficha de ${patient.first_name} ${patient.last_name}`}>Ver ficha<ChevronRight size={15} aria-hidden="true" /></Link></td></tr>)}
            </tbody></table></div>}
      {!loading && !error && data.total > 0 && <div className="patients-pagination"><span>{offset + 1}–{Math.min(offset + data.limit, data.total)} de {data.total} pacientes</span><div><button type="button" disabled={offset === 0} onClick={() => page(Math.max(0, offset - data.limit))}><ArrowLeft size={14} aria-hidden="true" />Anterior</button><button type="button" disabled={offset + data.limit >= data.total} onClick={() => page(offset + data.limit)}>Siguiente<ArrowRight size={14} aria-hidden="true" /></button></div></div>}
    </section>
  </section></ClinicalLayout>
}
