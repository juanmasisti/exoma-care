import { BookOpen, ChevronRight, Dna, LogOut, ShieldCheck, Stethoscope } from 'lucide-react'
import { Link } from 'react-router-dom'
import { setSession } from '../../services/session.js'
import './ClinicalLayout.css'

export default function ClinicalLayout({ session, children }) {
  const manager = session.role === 'medical_manager'
  const roleLabel = manager ? 'Gerente médico' : 'Médico tratante'
  const viewLabel = manager ? 'Catálogo de patologías' : 'Validación clínica'

  return <div className="clinical-shell">
    <a className="clinical-skip-link" href="#clinical-content">Ir al contenido</a>
    <aside className="clinical-sidebar" aria-label="Área clínica">
      <Link to="/catalogo/patologias" className="clinical-brand" aria-label="Exoma Care, catálogo clínico">
        <span className="clinical-brand-icon"><Dna size={28} aria-hidden="true" /></span>
        <span><strong>Exoma <span>Care</span></strong><small>MEDICINA DE PRECISIÓN</small></span>
      </Link>
      <div className="clinical-role"><span>Rol activo</span><strong><i aria-hidden="true" />{roleLabel}</strong></div>
      <nav className="clinical-navigation" aria-label="Navegación clínica">
        <p>{manager ? 'GESTIÓN MÉDICA' : 'CONSULTA CLÍNICA'}</p>
        <Link to="/catalogo/patologias" aria-current="page" className="clinical-nav-active">
          {manager ? <BookOpen size={19} aria-hidden="true" /> : <Stethoscope size={19} aria-hidden="true" />}
          <span><strong>{viewLabel}</strong><small>{manager ? 'Patologías y criterios' : 'Patologías y síntomas'}</small></span>
          <ChevronRight size={15} aria-hidden="true" />
        </Link>
      </nav>
      <div className="clinical-sidebar-footer">
        <div className="clinical-profile"><span className="clinical-avatar" aria-hidden="true">{manager ? 'GM' : 'MT'}</span>
          <span><strong>{roleLabel}</strong><small>{manager ? 'Administración del catálogo' : 'Consulta y validación'}</small></span>
        </div>
        <p><ShieldCheck size={14} aria-hidden="true" />Acceso según tu perfil</p>
      </div>
    </aside>
    <div className="clinical-workspace">
      <header className="clinical-topbar">
        <nav aria-label="Ubicación actual" className="clinical-breadcrumb"><span>Exoma Care</span><ChevronRight size={14} aria-hidden="true" /><strong>{viewLabel}</strong></nav>
        <button type="button" className="clinical-logout" onClick={() => setSession(null)}><LogOut size={15} aria-hidden="true" /><span>Cerrar sesión</span></button>
      </header>
      <main id="clinical-content" className="clinical-main" tabIndex={-1}>{children}</main>
    </div>
  </div>
}
