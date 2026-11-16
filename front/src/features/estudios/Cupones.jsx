import { useCallback, useEffect, useState } from 'react'
import { AlertCircle, CheckCircle2, Ticket } from 'lucide-react'
import ClinicalLayout from '../../components/layout/ClinicalLayout.jsx'
import { errorMessage } from '../../services/api.js'
import { listPatients } from '../pacientes/api.js'
import { assignCouponToPatient, assignCouponToPhysician, generateCoupons, listCouponPhysicians, listCoupons } from './api.js'
import { COUPON_STATUS_LABELS, percentLabel } from './format.js'
import './estudios.css'

const COPY = {
  medical_manager: ['Cupones de descuento', 'Generá lotes de cupones y asignalos a los médicos, que los reparten entre sus pacientes.'],
  treating_physician: ['Cupones de descuento', 'Cupones que te asignó la gerencia médica. Asignalos a tus pacientes.'],
  patient: ['Mis cupones', 'Cupones que te dio tu médico. Los aplicás al pagar un estudio.'],
  super_admin: ['Cupones de descuento', 'Vista general de los cupones.'],
}

// Cada rol solo ve los estados que le corresponden: el paciente no tiene por qué conocer el circuito interno.
const FILTER_STATUSES = {
  patient: ['paciente', 'usado'],
  treating_physician: ['medico', 'paciente', 'usado'],
}
const PATIENT_STATUS_LABELS = { paciente: 'Para usar', usado: 'Usado' }

export default function Cupones({ session }) {
  const role = session.role
  const manager = role === 'medical_manager'
  const physician = role === 'treating_physician'
  const [coupons, setCoupons] = useState(null)
  const [filter, setFilter] = useState('')
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [reload, setReload] = useState(0)
  const [title, subtitle] = COPY[role] || COPY.super_admin
  const filterStatuses = FILTER_STATUSES[role] || Object.keys(COUPON_STATUS_LABELS)
  const statusLabel = (value) => (role === 'patient' && PATIENT_STATUS_LABELS[value]) || COUPON_STATUS_LABELS[value] || value

  useEffect(() => {
    let active = true
    listCoupons(filter).then((data) => { if (active) { setCoupons(data); setError('') } })
      .catch((failure) => { if (active) setError(errorMessage(failure)) })
    return () => { active = false }
  }, [filter, reload])

  const refresh = useCallback((message) => { setNotice(message); setReload((n) => n + 1) }, [])

  return <ClinicalLayout session={session} pageLabel="Cupones"><section className="est-page">
    <header className="est-header"><div><span className="est-eyebrow">BONIFICACIONES</span><h1>{title}</h1><p>{subtitle}</p></div></header>
    {notice && <div role="status" className="est-success"><CheckCircle2 size={15} aria-hidden="true" /><p>{notice}</p></div>}
    <div className={manager ? 'est-grid' : ''}>
      <section className="est-card">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12, marginBottom: 16 }}>
          <h2 style={{ margin: 0 }}>Cupones {coupons ? `(${coupons.length})` : ''}</h2>
          <div><label className="est-sr-only" htmlFor="est-coupon-filter">Filtrar por estado</label>
            <select id="est-coupon-filter" value={filter} onChange={(event) => setFilter(event.target.value)}>
              <option value="">Todos los estados</option>
              {filterStatuses.map((value) => <option key={value} value={value}>{statusLabel(value)}</option>)}
            </select></div>
        </div>
        {error ? <div role="alert" className="est-error"><p>{error}</p><button type="button" onClick={() => { setError(''); setReload((n) => n + 1) }}>Reintentar</button></div>
          : !coupons ? <p role="status" className="est-loading">Cargando cupones...</p>
            : coupons.length === 0 ? <div className="est-empty"><Ticket size={36} aria-hidden="true" /><h3>No hay cupones</h3><p>{manager ? 'Generá un lote desde el panel de la derecha.' : physician ? 'Cuando la gerencia te asigne cupones, aparecen acá.' : 'Todavía no tenés cupones.'}</p></div>
              : <div className="est-table-scroll"><table className="est-table"><thead><tr><th>Código</th><th>Descuento</th><th>Estado</th>{(manager || physician) && <th>Asignación</th>}</tr></thead><tbody>
                {coupons.map((coupon) => <tr key={coupon.code}>
                  <td><strong>{coupon.code}</strong></td><td>{percentLabel(coupon.percentage)}</td>
                  <td><span className={`est-badge est-badge-${coupon.status === 'usado' ? 'neutral' : coupon.status === 'disponible' ? 'info' : 'success'}`}>{statusLabel(coupon.status)}</span></td>
                  {manager && <td>{coupon.status === 'disponible' ? <AssignToPhysician code={coupon.code} onDone={refresh} /> : coupon.physician_id ? `Médico #${coupon.physician_id}${coupon.patient_id ? ` → paciente #${coupon.patient_id}` : ''}` : '—'}</td>}
                  {physician && <td>{coupon.status === 'medico' ? <AssignToPatient code={coupon.code} onDone={refresh} /> : coupon.patient_id ? `Paciente #${coupon.patient_id}` : '—'}</td>}
                </tr>)}
              </tbody></table></div>}
      </section>
      {manager && <aside className="est-aside"><GenerateBatch onDone={refresh} /></aside>}
    </div>
  </section></ClinicalLayout>
}

function GenerateBatch({ onDone }) {
  const [quantity, setQuantity] = useState(5)
  const [percent, setPercent] = useState(10)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  async function submit(event) {
    event.preventDefault()
    setBusy(true); setError('')
    try { const created = await generateCoupons(Number(quantity), Number(percent)); onDone(`Se generaron ${created.length} cupón(es) del ${percentLabel(percent)}.`) } catch (failure) { setError(errorMessage(failure)) } finally { setBusy(false) }
  }

  return <form className="est-card" onSubmit={submit}>
    <h2>Generar lote</h2>
    {error && <div role="alert" className="est-error"><AlertCircle size={15} aria-hidden="true" /><p>{error}</p></div>}
    <div className="est-inline-form" style={{ marginTop: 0 }}>
      <div><label htmlFor="est-qty">Cantidad (1 a 100)</label><input id="est-qty" type="number" min="1" max="100" step="1" required value={quantity} onChange={(event) => setQuantity(event.target.value)} /></div>
      <div><label htmlFor="est-pct">Descuento % (mayor a 0, hasta 100)</label><input id="est-pct" type="number" min="1" max="100" step="any" required value={percent} onChange={(event) => setPercent(event.target.value)} /></div>
      <p className="est-help" style={{ margin: 0 }}>Cada cupón vence a los 30 días de generado.</p>
      <div className="est-actions"><button type="submit" className="est-primary" disabled={busy}>{busy ? 'Generando...' : 'Generar cupones'}</button></div>
    </div>
  </form>
}

function AssignToPhysician({ code, onDone }) {
  const [physicians, setPhysicians] = useState(null)
  const [selected, setSelected] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    let active = true
    listCouponPhysicians().then((data) => { if (active) setPhysicians(data) }).catch((failure) => { if (active) setError(errorMessage(failure)) })
    return () => { active = false }
  }, [])

  async function assign() {
    setBusy(true); setError('')
    try { await assignCouponToPhysician(code, Number(selected)); onDone(`Cupón ${code} asignado al médico.`) } catch (failure) { setError(errorMessage(failure)); setBusy(false) }
  }

  return <div style={{ display: 'flex', gap: 6, alignItems: 'center', minWidth: 260 }}>
    <label className="est-sr-only" htmlFor={`est-phys-${code}`}>Médico para el cupón {code}</label>
    <select id={`est-phys-${code}`} value={selected} onChange={(event) => setSelected(event.target.value)} disabled={!physicians}>
      <option value="">Elegir médico</option>
      {(physicians || []).map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
    </select>
    <button type="button" className="est-primary" disabled={!selected || busy} onClick={assign}>Asignar</button>
    {error && <span role="alert" style={{ color: '#9f1239', fontSize: 11 }}>{error}</span>}
  </div>
}

function AssignToPatient({ code, onDone }) {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState([])
  const [selected, setSelected] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    const controller = new AbortController()
    const timer = setTimeout(() => {
      listPatients(query, 0, controller.signal).then((data) => { if (!controller.signal.aborted) setResults(data.items) }).catch(() => {})
    }, 250)
    return () => { clearTimeout(timer); controller.abort() }
  }, [query])

  async function assign() {
    setBusy(true); setError('')
    try { await assignCouponToPatient(code, Number(selected)); onDone(`Cupón ${code} asignado al paciente.`) } catch (failure) { setError(errorMessage(failure)); setBusy(false) }
  }

  return <div style={{ display: 'grid', gap: 6, minWidth: 260 }}>
    <label className="est-sr-only" htmlFor={`est-pat-q-${code}`}>Buscar paciente para el cupón {code}</label>
    <input id={`est-pat-q-${code}`} type="search" placeholder="Buscar paciente" value={query} onChange={(event) => setQuery(event.target.value)} />
    <div style={{ display: 'flex', gap: 6 }}>
      <label className="est-sr-only" htmlFor={`est-pat-${code}`}>Paciente</label>
      <select id={`est-pat-${code}`} value={selected} onChange={(event) => setSelected(event.target.value)}>
        <option value="">Elegir paciente</option>
        {results.map((item) => <option key={item.id} value={item.id}>{item.last_name}, {item.first_name} · {item.dni}</option>)}
      </select>
      <button type="button" className="est-primary" disabled={!selected || busy} onClick={assign}>Asignar</button>
    </div>
    {error && <span role="alert" style={{ color: '#9f1239', fontSize: 11 }}>{error}</span>}
  </div>
}
