import { useParams } from 'react-router-dom'
import ClinicalLayout from '../../../components/layout/ClinicalLayout.jsx'
import EnvioLote from './EnvioLote.jsx'
import '../turnos/turnos.css'

// Base (decisión 016): T05 reemplaza este archivo con el detalle del lote; el envío lo pone T06 en EnvioLote.
export default function DetalleLote({ session }) {
  const { sampleSetId } = useParams()
  return <ClinicalLayout session={session} pageLabel={`Lote ${sampleSetId}`}>
    <header className="turnos-heading"><h1>Lote {sampleSetId}</h1></header>
    <div className="turnos-card"><p className="turnos-empty">En construcción.</p></div>
    <EnvioLote sampleSetId={sampleSetId} />
  </ClinicalLayout>
}
