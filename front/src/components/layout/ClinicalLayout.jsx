import { BookOpen, CalendarCheck, CalendarClock, ChevronRight, Dna, LogOut, ShieldCheck, Stethoscope, Users } from 'lucide-react'
import { Link, NavLink, useLocation } from 'react-router-dom'
import { setSession } from '../../services/session.js'
import './ClinicalLayout.css'

export default function ClinicalLayout({ session, children, pageLabel }) {
  const patient = session.role === 'patient'
  const manager = session.role === 'medical_manager'
  const roleLabel = patient ? 'Paciente' : manager ? 'Gerente médico' : 'Médico tratante'
  const location = useLocation()
  const patientsArea = location.pathname.startsWith('/medico/pacientes')
  const myAppointmentsArea = location.pathname === '/paciente/turnos' || location.pathname.startsWith('/paciente/estudios/')
  const viewLabel = patient ? (myAppointmentsArea ? 'Mis turnos' : 'Reservar turno') : patientsArea ? 'Pacientes' : manager ? 'Catálogo de patologías' : 'Validación clínica'
  const home = patient ? '/paciente/turnos/reservar' : manager ? '/catalogo/patologias' : '/medico/pacientes'
  const viewPath = patient ? (myAppointmentsArea ? '/paciente/turnos' : home) : patientsArea ? '/medico/pacientes' : '/catalogo/patologias'

  return <div className="clinical-shell">
    <a className="clinical-skip-link" href="#clinical-content">Ir al contenido</a>
    <aside className="clinical-sidebar" aria-label="Área clínica">
      <Link to={home} className="clinical-brand" aria-label="Exoma Care, inicio clínico">
        <span className="clinical-brand-icon"><Dna size={28} aria-hidden="true" /></span>
        <span><strong>Exoma <span>Care</span></strong><small>MEDICINA DE PRECISIÓN</small></span>
      </Link>
      <div className="clinical-role"><span>Rol activo</span><strong><i aria-hidden="true" />{roleLabel}</strong></div>
      <nav className="clinical-navigation" aria-label="Navegación clínica">
        <p>{patient ? 'PORTAL DEL PACIENTE' : manager ? 'GESTIÓN MÉDICA' : 'CONSULTA CLÍNICA'}</p>
        {patient && <NavLink to="/paciente/turnos" end className={({ isActive }) => isActive ? 'clinical-nav-active' : 'clinical-nav-link'}>
          <CalendarCheck size={19} aria-hidden="true" /><span><strong>Mis turnos</strong><small>Turnos reservados</small></span><ChevronRight size={15} aria-hidden="true" />
        </NavLink>}
        {patient && <NavLink to="/paciente/turnos/reservar" className={({ isActive }) => isActive ? 'clinical-nav-active' : 'clinical-nav-link'}>
          <CalendarClock size={19} aria-hidden="true" /><span><strong>Reservar turno</strong><small>Centro, fecha y horario</small></span><ChevronRight size={15} aria-hidden="true" />
        </NavLink>}
        {!manager && !patient && <NavLink to="/medico/pacientes" className={({ isActive }) => isActive ? 'clinical-nav-active' : 'clinical-nav-link'}>
          <Users size={19} aria-hidden="true" /><span><strong>Pacientes</strong><small>Gestión clínica y altas</small></span><ChevronRight size={15} aria-hidden="true" />
        </NavLink>}
        {!patient && <NavLink to="/catalogo/patologias" className={({ isActive }) => isActive ? 'clinical-nav-active' : 'clinical-nav-link'}>
          {manager ? <BookOpen size={19} aria-hidden="true" /> : <Stethoscope size={19} aria-hidden="true" />}
          <span><strong>{manager ? 'Catálogo de patologías' : 'Validación clínica'}</strong><small>Patologías y criterios</small></span><ChevronRight size={15} aria-hidden="true" />
        </NavLink>}
      </nav>
      <div className="clinical-sidebar-footer">
        <div className="clinical-profile"><span className="clinical-avatar" aria-hidden="true">{patient ? 'PA' : manager ? 'GM' : 'MT'}</span>
          <span><strong>{roleLabel}</strong><small>{patient ? 'Portal del paciente' : manager ? 'Administración del catálogo' : 'Gestión clínica'}</small></span>
        </div>
        <p><ShieldCheck size={14} aria-hidden="true" />Acceso según tu perfil</p>
      </div>
    </aside>
    <div className="clinical-workspace">
      <header className="clinical-topbar">
        <nav aria-label="Ubicación actual" className="clinical-breadcrumb"><span>Exoma Care</span><ChevronRight size={14} aria-hidden="true" /><Link to={viewPath}>{viewLabel}</Link>{pageLabel && <><ChevronRight size={14} aria-hidden="true" /><strong>{pageLabel}</strong></>}</nav>
        <button type="button" className="clinical-logout" onClick={() => setSession(null)}><LogOut size={15} aria-hidden="true" /><span>Cerrar sesión</span></button>
      </header>
      <main id="clinical-content" className="clinical-main" tabIndex={-1}>{children}</main>
    </div>
  </div>
}
