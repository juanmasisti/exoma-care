import { useSyncExternalStore } from 'react'
import { Link, Navigate, Route, Routes } from 'react-router-dom'
import Login from './Login.jsx'
import PathologyCatalog from './features/patologias/PathologyCatalog.jsx'
import { getSession, setSession, subscribeSession } from './services/session.js'

function App() {
  const session = useSyncExternalStore(subscribeSession, getSession)
  const catalogAccess = ['medical_manager', 'treating_physician'].includes(session?.role)

  return <Routes>
    <Route path="/" element={session ? <Navigate to={catalogAccess ? '/catalogo/patologias' : '/portal'} replace /> : <Login />} />
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
