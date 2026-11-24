import ClinicalLayout from '../../../components/layout/ClinicalLayout.jsx'
import '../turnos/turnos.css'

// Base (decisión 016): T05 reemplaza este archivo con los lotes armándose, cerrados y en viaje.
export default function ListaLotes({ session }) {
  return <ClinicalLayout session={session}>
    <header className="turnos-heading"><h1>Lotes</h1></header>
    <div className="turnos-card"><p className="turnos-empty">En construcción.</p></div>
  </ClinicalLayout>
}
