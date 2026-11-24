import ClinicalLayout from '../../../components/layout/ClinicalLayout.jsx'
import '../turnos/turnos.css'

// Base (decisión 016): T04 reemplaza este archivo con P1 a P9 y sus rutas internas bajo /transporte/*.
export default function Transportista({ session }) {
  return <ClinicalLayout session={session}>
    <header className="turnos-heading"><h1>Recorrido del día</h1></header>
    <div className="turnos-card"><p className="turnos-empty">En construcción.</p></div>
  </ClinicalLayout>
}
