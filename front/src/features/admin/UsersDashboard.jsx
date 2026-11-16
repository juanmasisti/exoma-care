import { useEffect, useMemo, useState } from 'react'
import { Check, CircleAlert, Copy, RefreshCw, ShieldCheck, UserPlus, Users } from 'lucide-react'
import ClinicalLayout from '../../components/layout/ClinicalLayout.jsx'
import { errorMessage } from '../../services/api.js'
import { createManagedUser, listManagedUsers } from '../../services/adminUsers.js'
import './usersDashboard.css'

const roles = [
  { value: 'treating_physician', label: 'Médico tratante', plural: 'Médicos tratantes' },
  { value: 'lab_administrator', label: 'Administrativo del laboratorio', plural: 'Administrativos del laboratorio' },
  { value: 'bioinformatician', label: 'Bioinformático', plural: 'Bioinformáticos' },
]

const emptyForm = () => ({
  role: 'treating_physician',
  first_name: '',
  last_name: '',
  email: '',
  phone: '',
  license_number: '',
  specialty: '',
})

const roleLabels = Object.fromEntries(roles.map(({ value, label }) => [value, label]))

export default function UsersDashboard({ session }) {
  const [users, setUsers] = useState([])
  const [form, setForm] = useState(emptyForm)
  const [temporaryPassword, setTemporaryPassword] = useState('')
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [copied, setCopied] = useState(false)
  const isPhysician = form.role === 'treating_physician'

  useEffect(() => {
    let active = true
    listManagedUsers().then((items) => {
      if (active) setUsers(items)
    }).catch((failure) => {
      if (active) setError(errorMessage(failure))
    }).finally(() => {
      if (active) setLoading(false)
    })
    return () => { active = false }
  }, [])

  const counts = useMemo(() => Object.fromEntries(
    roles.map(({ value }) => [value, users.filter((user) => user.role === value).length]),
  ), [users])

  function updateForm(field, value) {
    setForm((current) => ({ ...current, [field]: value }))
    setError('')
    setNotice('')
    setTemporaryPassword('')
  }

  async function submit(event) {
    event.preventDefault()
    setBusy(true)
    setError('')
    setNotice('')
    setTemporaryPassword('')
    setCopied(false)
    try {
      const created = await createManagedUser({
        ...form,
        email: form.email.trim(),
        first_name: form.first_name.trim(),
        last_name: form.last_name.trim(),
        phone: form.phone.trim(),
        license_number: isPhysician ? form.license_number.trim() : null,
        specialty: isPhysician ? form.specialty.trim() : null,
      })
      setUsers((current) => [...current, created].sort((a, b) => (
        a.last_name.localeCompare(b.last_name, 'es') || a.first_name.localeCompare(b.first_name, 'es')
      )))
      setTemporaryPassword(created.temporary_password)
      setNotice(`Se registró a ${created.first_name} ${created.last_name}.`)
      setForm(emptyForm())
    } catch (failure) {
      setError(errorMessage(failure))
    } finally {
      setBusy(false)
    }
  }

  async function copyPassword() {
    try {
      await navigator.clipboard.writeText(temporaryPassword)
      setCopied(true)
    } catch {
      setError('No se pudo copiar la contraseña. Seleccionala y copiala manualmente.')
    }
  }

  return <ClinicalLayout session={session} pageLabel="Administración de usuarios">
    <section className="users-page">
      <header className="users-header">
        <div>
          <p className="users-eyebrow">ADMINISTRACIÓN DEL SISTEMA</p>
          <h1>Usuarios y roles</h1>
          <p>Registrá al personal habilitado para trabajar en Exoma Care.</p>
        </div>
        <span className="users-header-badge"><ShieldCheck size={17} aria-hidden="true" />Acceso Super Admin</span>
      </header>

      <div className="users-summary" aria-label="Usuarios registrados por rol">
        {roles.map(({ value, label }) => <article key={value}>
          <span><Users size={19} aria-hidden="true" /></span>
          <strong>{loading ? '—' : counts[value]}</strong>
          <small>{counts[value] === 1 ? label : roles.find((role) => role.value === value).plural}</small>
        </article>)}
      </div>

      {error && <p className="users-feedback users-feedback--error" role="alert"><CircleAlert size={18} aria-hidden="true" />{error}</p>}
      {notice && <p className="users-feedback users-feedback--success" role="status"><Check size={18} aria-hidden="true" />{notice}</p>}
      {temporaryPassword && <aside className="users-password" aria-labelledby="temporary-password-title">
        <div><h2 id="temporary-password-title">Contraseña temporal (se muestra una sola vez)</h2>
          <p>Compartila con el usuario por un canal seguro. No se envió por email.</p></div>
        <code>{temporaryPassword}</code>
        <button type="button" onClick={copyPassword}><Copy size={16} aria-hidden="true" />{copied ? 'Copiada' : 'Copiar'}</button>
      </aside>}

      <div className="users-layout">
        <section className="users-card users-form-card" aria-labelledby="new-user-title">
          <div className="users-card-heading"><span><UserPlus size={19} aria-hidden="true" /></span><div><h2 id="new-user-title">Dar de alta usuario</h2><p>El email también será su identificador de acceso.</p></div></div>
          <form onSubmit={submit}>
            <fieldset disabled={busy}>
              <label htmlFor="user-role">Rol <span aria-hidden="true">*</span></label>
              <select id="user-role" value={form.role} onChange={(event) => {
                const nextRole = event.target.value
                setForm((current) => ({ ...current, role: nextRole, license_number: '', specialty: '' }))
                setTemporaryPassword('')
              }}>
                {roles.map(({ value, label }) => <option key={value} value={value}>{label}</option>)}
              </select>

              <div className="users-form-row">
                <div><label htmlFor="user-first-name">Nombre <span aria-hidden="true">*</span></label>
                  <input id="user-first-name" value={form.first_name} maxLength={100} required onChange={(event) => updateForm('first_name', event.target.value)} /></div>
                <div><label htmlFor="user-last-name">Apellido <span aria-hidden="true">*</span></label>
                  <input id="user-last-name" value={form.last_name} maxLength={100} required onChange={(event) => updateForm('last_name', event.target.value)} /></div>
              </div>
              <label htmlFor="user-email">Email / medio de contacto <span aria-hidden="true">*</span></label>
              <input id="user-email" type="email" autoComplete="email" maxLength={255} required value={form.email} onChange={(event) => updateForm('email', event.target.value)} />
              <label htmlFor="user-phone">Teléfono <span aria-hidden="true">*</span></label>
              <input id="user-phone" type="tel" autoComplete="tel" maxLength={30} required value={form.phone} onChange={(event) => updateForm('phone', event.target.value)} />

              {isPhysician && <>
                <label htmlFor="user-license">Matrícula <span aria-hidden="true">*</span></label>
                <input id="user-license" maxLength={50} required value={form.license_number} onChange={(event) => updateForm('license_number', event.target.value)} />
                <label htmlFor="user-specialty">Especialidad <span aria-hidden="true">*</span></label>
                <input id="user-specialty" maxLength={100} required value={form.specialty} onChange={(event) => updateForm('specialty', event.target.value)} />
              </>}

              <button className="users-submit" type="submit" disabled={busy}>
                {busy ? <RefreshCw size={17} className="users-spinner" aria-hidden="true" /> : <UserPlus size={17} aria-hidden="true" />}
                {busy ? 'Registrando...' : 'Registrar usuario'}
              </button>
            </fieldset>
          </form>
        </section>

        <section className="users-card users-list-card" aria-labelledby="registered-users-title">
          <div className="users-card-heading"><span><Users size={19} aria-hidden="true" /></span><div><h2 id="registered-users-title">Personal registrado</h2><p>{loading ? 'Cargando usuarios...' : `${users.length} usuario${users.length === 1 ? '' : 's'}`}</p></div></div>
          {loading ? <p className="users-empty"><RefreshCw size={20} className="users-spinner" aria-hidden="true" />Cargando personal...</p>
            : users.length === 0 ? <p className="users-empty">Todavía no hay usuarios registrados en estos roles.</p>
              : <ul className="users-list">{users.map((user) => <li key={user.id}>
                <span className="users-avatar" aria-hidden="true">{user.first_name[0]}{user.last_name[0]}</span>
                <span className="users-list-details"><strong>{user.first_name} {user.last_name}</strong><small>{user.email} · {user.phone}</small>
                  <small>{roleLabels[user.role]}{user.role === 'treating_physician' ? ` · ${user.specialty} · Mat. ${user.license_number}` : ''}</small>
                </span>
              </li>)}</ul>}
        </section>
      </div>
    </section>
  </ClinicalLayout>
}
