import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  ArrowRight,
  CircleAlert,
  Eye,
  EyeOff,
  Fingerprint,
  LockKeyhole,
  ShieldCheck,
} from 'lucide-react'
import dnaVideo from './assets/dna-background.mp4'
import dnaPoster from './assets/dna-poster.jpg'
import './Login.css'
import { login, errorMessage } from './services/api.js'

const roleRoutes = {
  paciente: '/paciente/dashboard',
  medico: '/medico/dashboard',
  administrativo: '/administrativo/dashboard',
  bioinformatico: '/bioinformatica/dashboard',
  gerente: '/gerente/dashboard',
}

function DnaBackground() {
  return (
    <div className="login-dna-scene" aria-hidden="true">
      <svg className="login-dna-filters" xmlns="http://www.w3.org/2000/svg">
        <filter id="dna-subject">
          <feColorMatrix
            type="matrix"
            values="1 0 0 0 0
                    0 1 0 0 0
                    0 0 1 0 0
                    0.2 0.8 0 0 0"
          />
          <feComponentTransfer>
            <feFuncA type="linear" slope="8" intercept="-0.55" />
          </feComponentTransfer>
          <feComposite in="SourceGraphic" operator="in" />
        </filter>
      </svg>
      <video
        className="login-dna-artwork"
        autoPlay
        loop
        muted
        playsInline
        poster={dnaPoster}
        aria-hidden="true"
      >
        <source src={dnaVideo} type="video/mp4" />
      </video>
    </div>
  )
}

function Login() {
  const [identifier, setIdentifier] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState('')
  const navigate = useNavigate()

  async function handleLogin(event) {
    event.preventDefault()
    setIsLoading(true)
    setError('')

    try {
      const user = await login(identifier, password)
      const destination = ['medical_manager', 'treating_physician'].includes(user.role)
        ? '/catalogo/patologias'
        : roleRoutes[user.rol?.toLowerCase()] ?? '/portal'

      navigate(destination)
    } catch (loginError) {
      setError(errorMessage(loginError))
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <main className="login-page">
      <DnaBackground />
      <section className="login-card" aria-labelledby="login-title">
        <div className="login-card__content">
          <div className="login-badge">
            <ShieldCheck size={15} aria-hidden="true" />
            <span>Acceso Seguro</span>
          </div>

          <h1 id="login-title">Iniciar sesión</h1>
          <p className="login-description">
            Accedé a tus estudios genéticos, turnos y seguimiento de muestras
            en tiempo real.
          </p>

          <form className="login-form" onSubmit={handleLogin}>
            <div className="login-field">
              <label htmlFor="identifier">Email</label>
              <div className="login-input-wrap">
                <Fingerprint
                  className="login-input-icon"
                  size={19}
                  aria-hidden="true"
                />
                <input
                  id="identifier"
                  name="identifier"
                  type="email"
                  autoComplete="username"
                  placeholder="nombre@ejemplo.com"
                  value={identifier}
                  onChange={(event) => setIdentifier(event.target.value)}
                  required
                />
              </div>
            </div>

            <div className="login-field">
              <div className="login-field__heading">
                <label htmlFor="password">Contraseña</label>
                <a className="login-forgot" href="/recuperar-contrasena">
                  ¿Olvidaste tu contraseña?
                </a>
              </div>
              <div className="login-input-wrap">
                <LockKeyhole
                  className="login-input-icon"
                  size={18}
                  aria-hidden="true"
                />
                <input
                  id="password"
                  name="password"
                  type={showPassword ? 'text' : 'password'}
                  autoComplete="current-password"
                  placeholder="Ingresá tu clave personal"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  required
                />
                <button
                  className="login-password-toggle"
                  type="button"
                  onClick={() => setShowPassword((visible) => !visible)}
                  aria-label={
                    showPassword ? 'Ocultar contraseña' : 'Mostrar contraseña'
                  }
                  aria-pressed={showPassword}
                >
                  {showPassword ? (
                    <EyeOff size={18} aria-hidden="true" />
                  ) : (
                    <Eye size={18} aria-hidden="true" />
                  )}
                </button>
              </div>
            </div>

            {error && (
              <p className="login-error" role="alert">
                <CircleAlert size={17} aria-hidden="true" />
                {error}
              </p>
            )}

            <button
              className="login-submit"
              type="submit"
              disabled={isLoading}
            >
              <span>{isLoading ? 'Cargando...' : 'Ingresar al portal'}</span>
              {!isLoading && <ArrowRight size={18} aria-hidden="true" />}
            </button>
          </form>

          <p className="login-security-note">
            <LockKeyhole size={14} aria-hidden="true" />
            Entorno médico cifrado y protegido
          </p>
        </div>
      </section>
    </main>
  )
}

export default Login
