import { Archive, BookOpen, CalendarClock, ChevronRight, ClipboardList, Dna, History, LayoutDashboard, LogOut, ShieldCheck, Stethoscope, UserCog, Users } from 'lucide-react'
import { Link, NavLink, useLocation, useSearchParams } from 'react-router-dom'
import { setSession } from '../../services/session.js'
import './ClinicalLayout.css'

export default function ClinicalLayout({ session, children, pageLabel, bioinformaticsCounts = {} }) {
  const patient = session.role === 'patient'
  const manager = session.role === 'medical_manager'
  const bioinformatician = session.role === 'bioinformatician'
  const superAdmin = session.role === 'super_admin'
  const roleLabel = patient ? 'Paciente' : manager ? 'Gerente médico' : bioinformatician ? 'Bioinformático' : superAdmin ? 'Super Admin' : 'Médico tratante'
  const location = useLocation()
  const [searchParams] = useSearchParams()
  const bioSection = searchParams.get('section') || 'inicio'
  const patientsArea = location.pathname.startsWith('/medico/pacientes')
  const bioSectionLabels = {
    inicio: 'Inicio / Dashboard',
    disponibles: 'Estudios disponibles',
    analisis: 'En análisis',
    historial: 'Historial',
  }
  const viewLabel = superAdmin ? 'Administración de usuarios' : patient ? 'Reservar turno' : bioinformatician ? bioSectionLabels[bioSection] || bioSectionLabels.inicio : patientsArea ? 'Pacientes' : manager ? 'Catálogo de patologías' : 'Validación clínica'
  const home = superAdmin ? '/super-admin/usuarios' : patient ? '/paciente/turnos/reservar' : bioinformatician ? '/bioinformatica/dashboard' : manager ? '/catalogo/patologias' : '/medico/pacientes'

  return <div className="clinical-shell">
    <a className="clinical-skip-link" href="#clinical-content">Ir al contenido</a>
    <aside className="clinical-sidebar" aria-label="Área clínica">
      <Link to={home} className="clinical-brand" aria-label="Exoma Care, inicio clínico">
        <span className="clinical-brand-icon"><Dna size={28} aria-hidden="true" /></span>
        <span><strong>Exoma <span>Care</span></strong><small>MEDICINA DE PRECISIÓN</small></span>
      </Link>
      <div className="clinical-role"><span>Rol activo</span><strong><i aria-hidden="true" />{roleLabel}</strong></div>
      <nav className="clinical-navigation" aria-label="Navegación clínica">
        <p>{superAdmin ? 'ADMINISTRACIÓN' : patient ? 'PORTAL DEL PACIENTE' : bioinformatician ? 'ANÁLISIS GENÓMICO' : manager ? 'GESTIÓN MÉDICA' : 'CONSULTA CLÍNICA'}</p>
        {superAdmin && <NavLink to={home} className={({ isActive }) => isActive ? 'clinical-nav-active' : 'clinical-nav-link'}>
          <UserCog size={19} aria-hidden="true" /><span><strong>Usuarios y roles</strong><small>Altas de personal</small></span><ChevronRight size={15} aria-hidden="true" />
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
        {!manager && !patient && !bioinformatician && !superAdmin && <NavLink to="/medico/pacientes" className={({ isActive }) => isActive ? 'clinical-nav-active' : 'clinical-nav-link'}>
          <Users size={19} aria-hidden="true" /><span><strong>Pacientes</strong><small>Gestión clínica y altas</small></span><ChevronRight size={15} aria-hidden="true" />
        </NavLink>}
        {!patient && !bioinformatician && !superAdmin && <NavLink to="/catalogo/patologias" className={({ isActive }) => isActive ? 'clinical-nav-active' : 'clinical-nav-link'}>
          {manager ? <BookOpen size={19} aria-hidden="true" /> : <Stethoscope size={19} aria-hidden="true" />}
          <span><strong>{manager ? 'Catálogo de patologías' : 'Validación clínica'}</strong><small>Patologías y criterios</small></span><ChevronRight size={15} aria-hidden="true" />
        </NavLink>}
      </nav>
      <div className="clinical-sidebar-footer">
        <div className="clinical-profile">        <span className="clinical-avatar" aria-hidden="true">{patient ? 'PA' : manager ? 'GM' : bioinformatician ? 'BI' : superAdmin ? 'SA' : 'MT'}</span>
        <span><strong>{roleLabel}</strong><small>{patient ? 'Portal del paciente' : manager ? 'Administración del catálogo' : bioinformatician ? 'Análisis genómico' : superAdmin ? 'Gestión de usuarios' : 'Gestión clínica'}</small></span>
        </div>
        <p><ShieldCheck size={14} aria-hidden="true" />Acceso según tu perfil</p>
      </div>
    </aside>
    <div className="clinical-workspace">
      <header className="clinical-topbar">
        <nav aria-label="Ubicación actual" className="clinical-breadcrumb"><span>Exoma Care</span><ChevronRight size={14} aria-hidden="true" /><Link to={superAdmin || patient ? home : patientsArea ? "/medico/pacientes" : "/catalogo/patologias"}>{viewLabel}</Link>{pageLabel && <><ChevronRight size={14} aria-hidden="true" /><strong>{pageLabel}</strong></>}</nav>
        <button type="button" className="clinical-logout" onClick={() => setSession(null)}><LogOut size={15} aria-hidden="true" /><span>Cerrar sesión</span></button>
      </header>
      <main id="clinical-content" className="clinical-main" tabIndex={-1}>{children}</main>
    </div>
  </div>
}
