import { useSyncExternalStore } from 'react'
import { Link, Navigate, Route, Routes } from 'react-router-dom'
import Login from './Login.jsx'
import PatientChat from './features/chatbot/PatientChat.jsx'
import PatientsList from './features/pacientes/PatientsList.jsx'
import PatientForm from './features/pacientes/PatientForm.jsx'
import PatientDetail from './features/pacientes/PatientDetail.jsx'
import PathologyCatalog from './features/patologias/PathologyCatalog.jsx'
import ReservarTurno from './features/logistica/turnos/ReservarTurno.jsx'
import BioinformaticsDashboard from './features/bioinformatica/BioinformaticsDashboard.jsx'
import UsersDashboard from './features/admin/UsersDashboard.jsx'
import DiaExtraccion from './features/logistica/turnos/DiaExtraccion.jsx'
import Seguimiento from './features/logistica/turnos/Seguimiento.jsx'
import MisTurnos from './features/logistica/turnos/MisTurnos.jsx'
import SimularAviso from './features/logistica/simulador/SimularAviso.jsx'
import { Cupones, NuevaSolicitud, SolicitudDetalle, SolicitudesList } from './features/estudios/index.js'
import { getSession, setSession, subscribeSession } from './services/session.js'

function App() {
  const session = useSyncExternalStore(subscribeSession, getSession)
  const physician = session?.role === 'treating_physician'
  const bioinformatician = session?.role === 'bioinformatician'
  const superAdmin = session?.role === 'super_admin'
  const labAdmin = session?.role === 'lab_administrator'
  const home = superAdmin ? '/super-admin/usuarios' : bioinformatician ? '/bioinformatica/dashboard' : physician ? '/medico/pacientes' : session?.role === 'medical_manager' ? '/catalogo/patologias' : labAdmin ? '/estudios' : '/portal'
  function roleRoute(roles, page) { return !session ? <Navigate to="/" replace /> : roles.includes(session.role) ? page : <Navigate to={home} replace /> }
  function patientPage(page) { return !session ? <Navigate to="/" replace /> : physician || superAdmin ? page : <Navigate to={home} replace /> }
  function patientPortalPage(page) { return !session ? <Navigate to="/" replace /> : session.role === 'patient' ? page : <Navigate to={home} replace /> }
  const catalogAccess = ['medical_manager', 'treating_physician', 'super_admin'].includes(session?.role)

  return <Routes>
    <Route path="/" element={session ? <Navigate to={home} replace /> : <Login />} />
    <Route path="/medico/pacientes" element={patientPage(<PatientsList session={session} />)} />
    <Route path="/medico/pacientes/nuevo" element={patientPage(<PatientForm key="new" session={session} />)} />
    <Route path="/medico/pacientes/:patientId" element={patientPage(<PatientDetail session={session} />)} />
    <Route path="/medico/pacientes/:patientId/editar" element={patientPage(<PatientForm key="edit" session={session} />)} />
    <Route path="/medico/dashboard" element={<Navigate to="/medico/pacientes" replace />} />
    <Route path="/login" element={<Navigate to="/" replace />} />
    <Route path="/estudios" element={roleRoute(['treating_physician', 'lab_administrator', 'patient', 'super_admin'], <SolicitudesList session={session} />)} />
    <Route path="/estudios/nuevo" element={roleRoute(['treating_physician'], <NuevaSolicitud session={session} />)} />
    <Route path="/estudios/:studyId" element={roleRoute(['treating_physician', 'lab_administrator', 'patient', 'super_admin'], <SolicitudDetalle key={session?.access_token} session={session} />)} />
    <Route path="/administrativo/simulador-bot" element={roleRoute(['lab_administrator'], <SimularAviso session={session} />)} />
    <Route path="/cupones" element={roleRoute(['medical_manager', 'treating_physician', 'patient', 'super_admin'], <Cupones session={session} />)} />
    <Route path="/catalogo/patologias" element={!session ? <Navigate to="/" replace /> : catalogAccess
      ? <PathologyCatalog session={session} /> : <Navigate to="/portal" replace />} />
    <Route path="/paciente/turnos/reservar" element={!session ? <Navigate to="/" replace /> : session.role === 'patient'
      ? <ReservarTurno session={session} /> : <Navigate to={home} replace />} />
    <Route path="/bioinformatica/dashboard" element={!session ? <Navigate to="/" replace /> : bioinformatician
      ? <BioinformaticsDashboard session={session} /> : <Navigate to={home} replace />} />
    <Route path="/super-admin/usuarios" element={!session ? <Navigate to="/" replace /> : superAdmin
      ? <UsersDashboard session={session} /> : <Navigate to={home} replace />} />
    <Route path="/paciente/consultas" element={patientPortalPage(<PatientChat key={session?.access_token} session={session} />)} />
    <Route path="/paciente/turnos" element={patientPortalPage(<MisTurnos session={session} />)} />
    <Route path="/paciente/estudios/:studyId/turno" element={patientPortalPage(<DiaExtraccion session={session} />)} />
    <Route path="/paciente/estudios/:studyId/seguimiento" element={patientPortalPage(<Seguimiento session={session} />)} />
    <Route path="*" element={!session ? <Navigate to="/" replace /> : <main style={{ padding: 32 }}>
      <h1>Sesión iniciada</h1><p>El portal de tu perfil todavía no está disponible en esta entrega.</p>
      {catalogAccess && <Link to="/catalogo/patologias">Consultar catálogo</Link>}
      {session.role === 'patient' && <Link to="/paciente/turnos/reservar">Reservar turno de extracción</Link>}
      {session.role === 'patient' && <p><Link to="/paciente/turnos">Mis turnos</Link></p>}
      {session.role === 'patient' && <p><Link to="/estudios">Mis estudios</Link></p>}
      {session.role === 'patient' && <p><Link to="/paciente/consultas">Consultas sobre estudios genéticos</Link></p>}
      <p><button type="button" onClick={() => setSession(null)}>Cerrar sesión</button></p>
    </main>} />
  </Routes>
}

export default App
