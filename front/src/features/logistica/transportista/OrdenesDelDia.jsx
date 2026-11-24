import ClinicalLayout from '../../../components/layout/ClinicalLayout.jsx'
import '../turnos/turnos.css'

// Base (decisión 016): T04 reemplaza este archivo con la generación y el listado de las órdenes del día.
export default function OrdenesDelDia({ session }) {
  return <ClinicalLayout session={session}>
    <header className="turnos-heading"><h1>Órdenes del día</h1></header>
    <div className="turnos-card"><p className="turnos-empty">En construcción.</p></div>
  </ClinicalLayout>
}
