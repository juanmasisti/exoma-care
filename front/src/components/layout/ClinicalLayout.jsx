import { Archive, BookOpen, CalendarCheck, CalendarClock, ChevronRight, ClipboardList, Dna, FileText, History, LayoutDashboard, LogOut, MessageCircle, ShieldCheck, Stethoscope, Ticket, UserCog, Users } from 'lucide-react'
import { Link, NavLink, useLocation, useSearchParams } from 'react-router-dom'
import { setSession } from '../../services/session.js'
import './ClinicalLayout.css'

export default function ClinicalLayout({ session, children, pageLabel, bioinformaticsCounts = {} }) {
  const patient = session.role === 'patient'
  const manager = session.role === 'medical_manager'
  const bioinformatician = session.role === 'bioinformatician'
  const superAdmin = session.role === 'super_admin'
  const labAdmin = session.role === 'lab_administrator'
  const physician = !patient && !manager && !bioinformatician && !superAdmin && !labAdmin
  const roleLabel = patient ? 'Paciente' : manager ? 'Gerente médico' : bioinformatician ? 'Bioinformático' : superAdmin ? 'Super Admin' : labAdmin ? 'Administrativo' : 'Médico tratante'
  const location = useLocation()
  const [searchParams] = useSearchParams()
  const bioSection = searchParams.get('section') || 'inicio'
  const patientsArea = location.pathname.startsWith('/medico/pacientes')
  const chatArea = location.pathname.startsWith('/paciente/consultas')
  const studiesArea = location.pathname.startsWith('/estudios')
  const couponsArea = location.pathname.startsWith('/cupones')
  const myAppointmentsArea = location.pathname === '/paciente/turnos' || location.pathname.startsWith('/paciente/estudios/')
  const bioSectionLabels = {
    inicio: 'Inicio / Dashboard',
    disponibles: 'Estudios disponibles',
    analisis: 'En análisis',
    historial: 'Historial',
  }
  const viewLabel = studiesArea ? (patient ? 'Mis estudios' : 'Solicitudes de estudio') : couponsArea ? (patient ? 'Mis cupones' : 'Cupones') : superAdmin ? 'Administración de usuarios' : patient ? (chatArea ? 'Consultas' : myAppointmentsArea ? 'Mis turnos' : 'Reservar turno') : bioinformatician ? bioSectionLabels[bioSection] || bioSectionLabels.inicio : patientsArea ? 'Pacientes' : manager ? 'Catálogo de patologías' : 'Validación clínica'
  const home = superAdmin ? '/super-admin/usuarios' : patient ? '/paciente/turnos/reservar' : bioinformatician ? '/bioinformatica/dashboard' : manager ? '/catalogo/patologias' : labAdmin ? '/estudios' : '/medico/pacientes'
  const viewPath = studiesArea ? '/estudios' : couponsArea ? '/cupones' : superAdmin
    ? home
    : patient
      ? (chatArea ? '/paciente/consultas' : myAppointmentsArea ? '/paciente/turnos' : home)
      : bioinformatician
        ? `${home}?section=${bioSection}`
        : patientsArea
          ? '/medico/pacientes'
          : '/catalogo/patologias'

  return <div className="clinical-shell">
    <a className="clinical-skip-link" href="#clinical-content">Ir al contenido</a>
    <aside className="clinical-sidebar" aria-label="Área clínica">
      <Link to={home} className="clinical-brand" aria-label="Exoma Care, inicio clínico">
        <span className="clinical-brand-icon"><Dna size={28} aria-hidden="true" /></span>
        <span><strong>Exoma <span>Care</span></strong><small>MEDICINA DE PRECISIÓN</small></span>
      </Link>
      <div className="clinical-role"><span>Rol activo</span><strong><i aria-hidden="true" />{roleLabel}</strong></div>
      <nav className="clinical-navigation" aria-label="Navegación clínica">
        <p>{superAdmin ? 'ADMINISTRACIÓN' : patient ? 'PORTAL DEL PACIENTE' : bioinformatician ? 'ANÁLISIS GENÓMICO' : manager ? 'GESTIÓN MÉDICA' : labAdmin ? 'GESTIÓN ADMINISTRATIVA' : 'CONSULTA CLÍNICA'}</p>
        {superAdmin && <NavLink to={home} className={({ isActive }) => isActive ? 'clinical-nav-active' : 'clinical-nav-link'}>
          <UserCog size={19} aria-hidden="true" /><span><strong>Usuarios y roles</strong><small>Altas de personal</small></span><ChevronRight size={15} aria-hidden="true" />
        </NavLink>}
        {(patient || labAdmin || superAdmin) && <NavLink to="/estudios" className={({ isActive }) => isActive ? 'clinical-nav-active' : 'clinical-nav-link'}>
          <FileText size={19} aria-hidden="true" /><span><strong>{patient ? 'Mis estudios' : 'Solicitudes de estudio'}</strong><small>{patient ? 'Presupuesto y pagos' : 'Presupuestos y coberturas'}</small></span><ChevronRight size={15} aria-hidden="true" />
        </NavLink>}
        {patient && <NavLink to="/paciente/consultas" className={({ isActive }) => isActive ? 'clinical-nav-active' : 'clinical-nav-link'}>
          <MessageCircle size={19} aria-hidden="true" /><span><strong>Consultas</strong><small>Estudios genéticos y patologías</small></span><ChevronRight size={15} aria-hidden="true" />
        </NavLink>}
        {patient && <NavLink to="/paciente/turnos" end className={({ isActive }) => isActive ? 'clinical-nav-active' : 'clinical-nav-link'}>
          <CalendarCheck size={19} aria-hidden="true" /><span><strong>Mis turnos</strong><small>Turnos reservados</small></span><ChevronRight size={15} aria-hidden="true" />
        </NavLink>}
        {patient && <NavLink to="/paciente/turnos/reservar" className={({ isActive }) => isActive ? 'clinical-nav-active' : 'clinical-nav-link'}>
          <CalendarClock size={19} aria-hidden="true" /><span><strong>Reservar turno</strong><small>Centro, fecha y horario</small></span><ChevronRight size={15} aria-hidden="true" />
        </NavLink>}
        {bioinformatician && <>
          {[
            ['inicio', 'Inicio / Dashboard', LayoutDashboard, bioinformaticsCounts.total],
            ['disponibles', 'Estudios disponibles', Archive, bioinformaticsCounts.available],
            ['analisis', 'En análisis', ClipboardList, bioinformaticsCounts.analyzing],
            ['historial', 'Historial', History, bioinformaticsCounts.history],
          ].map(([section, label, Icon, count]) => (
            <Link
              key={section}
              to={`/bioinformatica/dashboard?section=${section}`}
              className={bioSection === section ? 'clinical-nav-active' : 'clinical-nav-link'}
              aria-current={bioSection === section ? 'page' : undefined}
            >
              <Icon size={19} aria-hidden="true" />
              <span><strong>{label}</strong></span>
              {Number.isInteger(count) && <small className="clinical-nav-count">{count}</small>}
            </Link>
          ))}
        </>}
        {physician && <NavLink to="/estudios" className={({ isActive }) => isActive ? 'clinical-nav-active' : 'clinical-nav-link'}>
          <FileText size={19} aria-hidden="true" /><span><strong>Solicitudes de estudio</strong><small>Pedidos y presupuestos</small></span><ChevronRight size={15} aria-hidden="true" />
        </NavLink>}
        {(physician || manager || patient || superAdmin) && <NavLink to="/cupones" className={({ isActive }) => isActive ? 'clinical-nav-active' : 'clinical-nav-link'}>
          <Ticket size={19} aria-hidden="true" /><span><strong>{patient ? 'Mis cupones' : 'Cupones'}</strong><small>Descuentos en estudios</small></span><ChevronRight size={15} aria-hidden="true" />
        </NavLink>}
        {physician && <NavLink to="/medico/pacientes" className={({ isActive }) => isActive ? 'clinical-nav-active' : 'clinical-nav-link'}>
          <Users size={19} aria-hidden="true" /><span><strong>Pacientes</strong><small>Gestión clínica y altas</small></span><ChevronRight size={15} aria-hidden="true" />
        </NavLink>}
        {!patient && !bioinformatician && !superAdmin && !labAdmin && <NavLink to="/catalogo/patologias" className={({ isActive }) => isActive ? 'clinical-nav-active' : 'clinical-nav-link'}>
          {manager ? <BookOpen size={19} aria-hidden="true" /> : <Stethoscope size={19} aria-hidden="true" />}
          <span><strong>{manager ? 'Catálogo de patologías' : 'Validación clínica'}</strong><small>Patologías y criterios</small></span><ChevronRight size={15} aria-hidden="true" />
        </NavLink>}
      </nav>
      <div className="clinical-sidebar-footer">
        <div className="clinical-profile">        <span className="clinical-avatar" aria-hidden="true">{patient ? 'PA' : manager ? 'GM' : bioinformatician ? 'BI' : superAdmin ? 'SA' : labAdmin ? 'AD' : 'MT'}</span>
        <span><strong>{roleLabel}</strong><small>{patient ? 'Portal del paciente' : manager ? 'Administración del catálogo' : bioinformatician ? 'Análisis genómico' : superAdmin ? 'Gestión de usuarios' : labAdmin ? 'Gestión administrativa' : 'Gestión clínica'}</small></span>
        </div>
        <p><ShieldCheck size={14} aria-hidden="true" />Acceso según tu perfil</p>
      </div>
    </aside>
    <div className="clinical-workspace">
      <header className="clinical-topbar">
        <nav aria-label="Ubicación actual" className="clinical-breadcrumb"><span>Exoma Care</span><ChevronRight size={14} aria-hidden="true" /><Link to={viewPath}>{viewLabel}</Link>{pageLabel && pageLabel !== viewLabel && <><ChevronRight size={14} aria-hidden="true" /><strong>{pageLabel}</strong></>}</nav>
        <button type="button" className="clinical-logout" onClick={() => setSession(null)}><LogOut size={15} aria-hidden="true" /><span>Cerrar sesión</span></button>
      </header>
      <main id="clinical-content" className="clinical-main" tabIndex={-1}>{children}</main>
    </div>
  </div>
}
