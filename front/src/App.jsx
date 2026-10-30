import { useSyncExternalStore } from 'react'
import { Link, Navigate, Route, Routes } from 'react-router-dom'
import Login from './Login.jsx'
import PatientsList from './features/pacientes/PatientsList.jsx'
import PatientForm from './features/pacientes/PatientForm.jsx'
import PatientDetail from './features/pacientes/PatientDetail.jsx'
import PathologyCatalog from './features/patologias/PathologyCatalog.jsx'
import { getSession, setSession, subscribeSession } from './services/session.js'

function App() {
  const session = useSyncExternalStore(subscribeSession, getSession)
  const physician = session?.role === 'treating_physician'
  const home = physician ? '/medico/pacientes' : session?.role === 'medical_manager' ? '/catalogo/patologias' : '/portal'
  function patientPage(page) { return !session ? <Navigate to="/" replace /> : physician ? page : <Navigate to={home} replace /> }
  const catalogAccess = ['medical_manager', 'treating_physician'].includes(session?.role)

  return <Routes>
    <Route path="/" element={session ? <Navigate to={home} replace /> : <Login />} />
    <Route path="/medico/pacientes" element={patientPage(<PatientsList session={session} />)} />
    <Route path="/medico/pacientes/nuevo" element={patientPage(<PatientForm key="new" session={session} />)} />
    <Route path="/medico/pacientes/:patientId" element={patientPage(<PatientDetail session={session} />)} />
    <Route path="/medico/pacientes/:patientId/editar" element={patientPage(<PatientForm key="edit" session={session} />)} />
    <Route path="/medico/dashboard" element={<Navigate to="/medico/pacientes" replace />} />
    <Route path="/login" element={<Navigate to="/" replace />} />
    <Route path="/catalogo/patologias" element={!session ? <Navigate to="/" replace /> : catalogAccess
      ? <PathologyCatalog session={session} /> : <Navigate to="/portal" replace />} />
    <Route path="*" element={!session ? <Navigate to="/" replace /> : <main style={{ padding: 32 }}>
      <h1>Sesión iniciada</h1><p>El portal de tu perfil todavía no está disponible en esta entrega.</p>
      {catalogAccess && <Link to="/catalogo/patologias">Consultar catálogo</Link>}
      <p><button type="button" onClick={() => setSession(null)}>Cerrar sesión</button></p>
    </main>} />
  </Routes>
}

export default App
