import { useEffect, useState } from 'react'
import { ChevronRight, ClipboardList, Plus } from 'lucide-react'
import { Link } from 'react-router-dom'
import ClinicalLayout from '../../components/layout/ClinicalLayout.jsx'
import { errorMessage } from '../../services/api.js'
import { listStudyRequests } from './api.js'
import { dateTime, statusLabel, statusTone } from './format.js'
import './estudios.css'

const COPY = {
  treating_physician: ['Solicitudes de estudio', 'Estudios que pediste para tus pacientes y su estado de pago.'],
  lab_administrator: ['Solicitudes de estudio', 'Emití presupuestos y gestioná las coberturas de obra social.'],
  patient: ['Mis estudios', 'Seguí tus estudios, abonalos o consultá la cobertura de tu obra social.'],
  super_admin: ['Solicitudes de estudio', 'Vista general de las solicitudes.'],
}

export default function SolicitudesList({ session }) {
  const [studies, setStudies] = useState(null)
  const [error, setError] = useState('')
  const [retry, setRetry] = useState(0)
  const physician = session.role === 'treating_physician'
  const patient = session.role === 'patient'
  const [title, subtitle] = COPY[session.role] || COPY.super_admin

  useEffect(() => {
    let active = true
    listStudyRequests().then((data) => { if (active) setStudies(data) })
      .catch((failure) => { if (active) setError(errorMessage(failure)) })
    return () => { active = false }
  }, [retry])

  return <ClinicalLayout session={session}><section className="est-page">
    <header className="est-header"><div><span className="est-eyebrow">ESTUDIOS GENÉTICOS</span><h1>{title}</h1><p>{subtitle}</p></div>
      {physician && <Link to="/estudios/nuevo" className="est-primary"><Plus size={16} aria-hidden="true" />Nueva solicitud</Link>}
    </header>
    <section className="est-card">
      {error ? <div role="alert" className="est-error"><p>{error}</p><button type="button" onClick={() => { setError(''); setRetry((n) => n + 1) }}>Reintentar</button></div>
        : !studies ? <p role="status" className="est-loading">Cargando solicitudes...</p>
          : studies.length === 0 ? <div className="est-empty"><ClipboardList size={36} aria-hidden="true" /><h3>Todavía no hay solicitudes</h3><p>{physician ? 'Creá la primera desde "Nueva solicitud".' : patient ? 'Cuando tu médico pida un estudio, lo vas a ver acá.' : 'Cuando los médicos creen solicitudes, aparecen acá.'}</p></div>
            : <div className="est-table-scroll"><table className="est-table"><thead><tr><th>Estudio</th>{!patient && <th>Paciente</th>}<th>Patologías</th><th>Genes</th><th>Estado</th><th>Creado</th><th><span className="est-sr-only">Acciones</span></th></tr></thead><tbody>
              {studies.map((study) => <tr key={study.id}>
                <td><strong>#{study.id}</strong></td>
                {!patient && <td>{study.patient_name || `Paciente ${study.patient_id}`}</td>}
                <td>{study.pathologies.map((item) => item.name).join(' · ')}</td>
                <td>{study.gene_count}</td>
                <td><span className={`est-badge est-badge-${statusTone(study.status)}`}>{statusLabel(study.status)}</span></td>
                <td>{dateTime(study.created_at)}</td>
                <td><Link to={`/estudios/${study.id}`} className="est-link">Ver detalle<ChevronRight size={14} aria-hidden="true" /></Link></td>
              </tr>)}
            </tbody></table></div>}
    </section>
  </section></ClinicalLayout>
}
