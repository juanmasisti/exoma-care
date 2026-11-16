import { useCallback, useEffect, useState } from 'react'
import { AlertCircle, ArrowLeft, CheckCircle2, Dna } from 'lucide-react'
import { Link, useParams } from 'react-router-dom'
import ClinicalLayout from '../../components/layout/ClinicalLayout.jsx'
import { errorMessage } from '../../services/api.js'
import {
  authorizeCoverage, choosePaymentMode, getStudyRequest, issueBudget, listCoupons, listInsurers,
  payStudy, rejectCoverage, submitDemand,
} from './api.js'
import { dateTime, money, percentLabel, statusLabel, statusTone } from './format.js'
import './estudios.css'

const COVERAGE_LABELS = { pendiente: 'Pendiente', autorizada: 'Autorizada', rechazada: 'Rechazada', demanda_en_curso: 'Demanda en curso' }
const OPERATION_LABELS = { cobro_paciente: 'Cobro al paciente', cobertura_obra_social: 'Cobertura de obra social' }
const OPERATION_STATUS = { registrada: 'Registrada', registrando: 'En curso', a_cobrar: 'A cobrar a la obra social' }

export default function SolicitudDetalle({ session }) {
  const { studyId } = useParams()
  const [study, setStudy] = useState(null)
  const [error, setError] = useState('')
  const [actionError, setActionError] = useState('')
  const [busy, setBusy] = useState(false)
  const [retry, setRetry] = useState(0)
  const role = session.role
  const admin = role === 'lab_administrator' || role === 'super_admin'
  const patient = role === 'patient'

  useEffect(() => {
    let active = true
    getStudyRequest(studyId).then((data) => { if (active) setStudy(data) })
      .catch((failure) => { if (active) setError(errorMessage(failure)) })
    return () => { active = false }
  }, [studyId, retry])

  // Todas las acciones devuelven el detalle actualizado del estudio.
  const run = useCallback(async (action) => {
    setBusy(true); setActionError('')
    try { setStudy(await action()); return true } catch (failure) { setActionError(errorMessage(failure)); return false } finally { setBusy(false) }
  }, [])

  const budget = study?.budget
  const split = budget?.split

  return <ClinicalLayout session={session} pageLabel={study ? `Estudio #${study.id}` : 'Estudio'}><section className="est-page">
    <Link to="/estudios" className="est-back"><ArrowLeft size={14} aria-hidden="true" />Volver a las solicitudes</Link>
    {error ? <div role="alert" className="est-error"><p>{error}</p><button type="button" onClick={() => { setError(''); setRetry((n) => n + 1) }}>Reintentar</button></div>
      : !study ? <p role="status" className="est-loading">Cargando estudio...</p> : <>
        <header className="est-header"><div><span className="est-eyebrow">ESTUDIO GENÉTICO</span><h1>Estudio #{study.id}</h1><p>{study.patient_name || `Paciente ${study.patient_id}`} · creado el {dateTime(study.created_at)}</p></div>
          <span className={`est-badge est-badge-${statusTone(study.status)}`}>{statusLabel(study.status)}</span>
        </header>
        <div className="est-grid">
          <div className="est-stack">
            <section className="est-card">
              <h2>Pedido</h2>
              <dl className="est-dl">
                <dt>Patologías</dt><dd>{study.pathologies.map((item) => item.name).join(' · ')}</dd>
                <dt>Genes ({study.genes.length})</dt>
                <dd><ul className="est-chips">{study.genes.map((gene) => <li key={gene.symbol} className={`est-chip ${gene.origin === 'catalogo' ? 'est-chip-catalog' : ''}`}>{gene.origin === 'catalogo' && <Dna size={12} aria-hidden="true" />}{gene.symbol}{gene.origin === 'manual' && <small style={{ margin: 0 }}>agregado</small>}</li>)}</ul></dd>
                <dt>Hallazgos secundarios</dt><dd>{study.include_secondary_findings ? 'Se incluye la búsqueda' : 'No se incluyen'}</dd>
              </dl>
            </section>

            <section className="est-card">
              <h2>Presupuesto</h2>
              {!budget ? <p className="est-help" style={{ margin: 0 }}>Todavía no se emitió el presupuesto.{study.estimated_budget && <> Estimado según los genes: <strong>{money(study.estimated_budget.total_cents)}</strong>.</>}</p> : <>
                <ul className="est-lines">
                  <li><span>Base (hasta 5 genes)</span><strong>{money(budget.base_cents)}</strong></li>
                  <li><span>{budget.extra_genes} gen(es) adicional(es)</span><strong>{money(budget.extra_cents)}</strong></li>
                  <li className="est-total"><span>Total</span><strong>{money(budget.total_cents)}</strong></li>
                </ul>
                {split && <>
                  <h3>Reparto {split.estimated && '(estimado)'}</h3>
                  <ul className="est-lines">
                    <li><span>Cubre la obra social{budget.insurer ? ` (${budget.insurer.name})` : ''}{budget.coverage_percent !== null ? ` · ${percentLabel(budget.coverage_percent)}` : ''}</span><strong>{money(split.insurer_cents)}</strong></li>
                    <li><span>A cargo del paciente</span><strong>{money(split.patient_cents)}</strong></li>
                  </ul>
                  {split.estimated && <p className="est-help">El porcentaje se confirma cuando la obra social autoriza la cobertura.</p>}
                </>}
              </>}
            </section>

            {study.coverage && <section className="est-card">
              <h2>Cobertura de obra social</h2>
              <dl className="est-dl">
                <dt>Estado</dt><dd>{COVERAGE_LABELS[study.coverage.status] || study.coverage.status}</dd>
                {study.coverage.rejection_reason && <><dt>Motivo del rechazo</dt><dd>{study.coverage.rejection_reason}</dd></>}
                <dt>Demandas presentadas</dt><dd>{study.coverage.demands_count}</dd>
              </dl>
            </section>}

            {study.operations.length > 0 && <section className="est-card">
              <h2>Operaciones financieras</h2>
              <div className="est-table-scroll"><table className="est-table"><thead><tr><th>Operación</th><th>Estado</th><th>Importe</th><th>Descuento</th><th>Fecha</th></tr></thead><tbody>
                {study.operations.map((op) => <tr key={op.id}>
                  <td>{OPERATION_LABELS[op.type] || op.type}{op.coupon_code && <small>Cupón {op.coupon_code}</small>}{op.insurer_name && <small>{op.insurer_name}</small>}</td>
                  <td>{OPERATION_STATUS[op.status] || op.status}</td><td>{money(op.amount_cents)}</td><td>{op.discount_cents ? money(op.discount_cents) : '—'}</td><td>{dateTime(op.created_at)}</td>
                </tr>)}
              </tbody></table></div>
            </section>}
          </div>

          <aside className="est-aside" aria-label="Próximo paso">
            <section className="est-card">
              <h2>Próximo paso</h2>
              {actionError && <div role="alert" className="est-error"><AlertCircle size={15} aria-hidden="true" /><p>{actionError}</p></div>}
              <NextStep study={study} admin={admin} patient={patient} busy={busy} run={run} />
            </section>
          </aside>
        </div>
      </>}
  </section></ClinicalLayout>
}

function NextStep({ study, admin, patient, busy, run }) {
  const { status, budget, coverage } = study
  if (status === 'creado' && !budget) {
    return admin ? <><p className="est-help" style={{ marginTop: 0 }}>Emití el presupuesto con el costo según la cantidad de genes.</p>
      <div className="est-actions"><button type="button" className="est-primary" disabled={busy} onClick={() => run(() => issueBudget(study.id))}>{busy ? 'Emitiendo...' : 'Emitir presupuesto'}</button></div></>
      : <p className="est-help" style={{ marginTop: 0 }}>Administración todavía tiene que emitir el presupuesto.</p>
  }
  if (status === 'creado' && patient) return <PaymentModeForm study={study} busy={busy} run={run} />
  if (status === 'creado') return <p className="est-help" style={{ marginTop: 0 }}>El paciente tiene que elegir cómo abonar el estudio.</p>
  if (status === 'pendiente_autorizacion') {
    return admin ? <CoverageReview study={study} busy={busy} run={run} />
      : <p className="est-help" style={{ marginTop: 0 }}>{coverage?.status === 'demanda_en_curso' ? 'La demanda fue presentada: administración la está revisando.' : 'Administración está gestionando la autorización con la obra social.'}</p>
  }
  if (status === 'rechazado') {
    return patient ? <RejectedOptions study={study} busy={busy} run={run} />
      : <p className="est-help" style={{ marginTop: 0 }}>La obra social rechazó la cobertura. El paciente puede presentar una demanda o pagar como particular.</p>
  }
  if (status === 'pendiente_pago') return patient ? <PayForm study={study} busy={busy} run={run} />
    : <p className="est-help" style={{ marginTop: 0 }}>Falta que el paciente abone {money(budget?.split?.patient_cents)}.</p>
  if (status === 'pagado' || status === 'autorizado') {
    return <><div className="est-success"><CheckCircle2 size={16} aria-hidden="true" /><p>{status === 'pagado' ? 'Estudio pagado.' : 'Estudio autorizado.'} Ya está habilitado para sacar turno de extracción.</p></div>
      {patient && <div className="est-actions"><Link to="/paciente/turnos/reservar" className="est-primary">Reservar turno</Link></div>}</>
  }
  return <p className="est-help" style={{ marginTop: 0 }}>El estudio avanzó a «{statusLabel(status)}».</p>
}

function PaymentModeForm({ study, busy, run }) {
  const [mode, setMode] = useState('particular')
  const [insurers, setInsurers] = useState(null)
  const [insurerId, setInsurerId] = useState('')
  const [loadError, setLoadError] = useState('')

  useEffect(() => {
    if (mode !== 'obra_social' || insurers) return undefined
    let active = true
    listInsurers().then((data) => { if (active) setInsurers(data) }).catch((failure) => { if (active) setLoadError(errorMessage(failure)) })
    return () => { active = false }
  }, [mode, insurers])

  return <form className="est-inline-form" onSubmit={(event) => { event.preventDefault(); run(() => choosePaymentMode(study.id, mode, insurerId)) }}>
    <p className="est-help" style={{ margin: 0 }}>Total del estudio: <strong>{money(study.budget.total_cents)}</strong>. Elegí cómo lo abonás.</p>
    <label className={`est-option ${mode === 'particular' ? 'est-selected' : ''}`}><input type="radio" name="mode" checked={mode === 'particular'} onChange={() => setMode('particular')} /><span><strong>Pago particular</strong><small>Abonás el total con tarjeta (simulado).</small></span></label>
    <label className={`est-option ${mode === 'obra_social' ? 'est-selected' : ''}`}><input type="radio" name="mode" checked={mode === 'obra_social'} onChange={() => setMode('obra_social')} /><span><strong>Obra social</strong><small>La obra social cubre su parte y abonás el resto como particular.</small></span></label>
    {mode === 'obra_social' && <div>
      <label htmlFor="est-insurer">Obra social</label>
      {loadError ? <div role="alert" className="est-error"><p>{loadError}</p></div>
        : !insurers ? <p role="status" className="est-help">Cargando obras sociales...</p>
          : <select id="est-insurer" value={insurerId} onChange={(event) => setInsurerId(event.target.value)} required>
            <option value="">Elegí una obra social</option>
            {insurers.map((item) => <option key={item.id} value={item.id}>{item.name}{item.acronym ? ` (${item.acronym})` : ''}{item.default_coverage_percent !== null ? ` · cobertura ${percentLabel(item.default_coverage_percent)}` : ''}</option>)}
          </select>}
    </div>}
    <div className="est-actions"><button type="submit" className="est-primary" disabled={busy || (mode === 'obra_social' && !insurerId)}>{busy ? 'Guardando...' : 'Confirmar modalidad'}</button></div>
  </form>
}

function CoverageReview({ study, busy, run }) {
  const [percent, setPercent] = useState('')
  const [reason, setReason] = useState('')
  const needsPercent = study.coverage?.status === 'demanda_en_curso'
  const parsed = percent === '' ? null : Number(percent)
  const invalidPercent = parsed !== null && (Number.isNaN(parsed) || parsed < 0 || parsed > 100)

  return <div className="est-inline-form">
    {needsPercent && <div className="est-note"><AlertCircle size={15} aria-hidden="true" /><p>El paciente presentó una demanda. Para autorizar hay que indicar el porcentaje de cobertura.</p></div>}
    {needsPercent ? <div>
      <label htmlFor="est-percent">Porcentaje de cobertura</label>
      <input id="est-percent" type="number" min="0" max="100" step="any" value={percent} placeholder="Ej. 60" onChange={(event) => setPercent(event.target.value)} />
    </div>
      : <p className="est-help" style={{ margin: 0 }}>La cobertura la define la obra social{study.budget?.coverage_percent != null ? ` (porcentaje de referencia: ${percentLabel(study.budget.coverage_percent)})` : ''}: al autorizar se toma el porcentaje que informa su API.</p>}
    <div className="est-actions"><button type="button" className="est-primary" disabled={busy || invalidPercent || (needsPercent && parsed === null)} onClick={() => run(() => authorizeCoverage(study.id, parsed))}>{busy ? 'Procesando...' : 'Autorizar cobertura'}</button></div>
    <div>
      <label htmlFor="est-reason">Motivo del rechazo</label>
      <textarea id="est-reason" rows={3} maxLength={500} value={reason} onChange={(event) => setReason(event.target.value)} />
    </div>
    <div className="est-actions"><button type="button" className="est-danger" disabled={busy || !reason.trim()} onClick={() => run(() => rejectCoverage(study.id, reason.trim()))}>Rechazar cobertura</button></div>
  </div>
}

function RejectedOptions({ study, busy, run }) {
  const [file, setFile] = useState(null)
  const [fileError, setFileError] = useState('')

  function pick(event) {
    const chosen = event.target.files?.[0] || null
    setFileError('')
    if (chosen && chosen.size > 5 * 1024 * 1024) { setFileError('El PDF no puede superar los 5 MB.'); setFile(null); return }
    setFile(chosen)
  }

  return <div className="est-inline-form">
    <div className="est-error" style={{ margin: 0 }}><AlertCircle size={15} aria-hidden="true" /><p>La obra social rechazó la cobertura{study.coverage?.rejection_reason ? `: ${study.coverage.rejection_reason}` : '.'}</p></div>
    <div>
      <label htmlFor="est-demand">Presentar demanda (PDF, hasta 5 MB)</label>
      <input id="est-demand" type="file" accept="application/pdf" onChange={pick} />
      {fileError && <p className="est-help" role="alert" style={{ color: '#9f1239' }}>{fileError}</p>}
    </div>
    <div className="est-actions"><button type="button" className="est-primary" disabled={busy || !file} onClick={() => run(() => submitDemand(study.id, file))}>{busy ? 'Enviando...' : 'Presentar demanda'}</button></div>
    <p className="est-help" style={{ margin: 0 }}>O abonás el estudio como particular:</p>
    <div className="est-actions"><button type="button" disabled={busy} onClick={() => run(() => choosePaymentMode(study.id, 'particular'))}>Pagar como particular</button></div>
  </div>
}

function PayForm({ study, busy, run }) {
  const [coupons, setCoupons] = useState(null)
  const [code, setCode] = useState('')
  const [loadError, setLoadError] = useState('')

  useEffect(() => {
    let active = true
    listCoupons('paciente').then((data) => { if (active) setCoupons(data) }).catch((failure) => { if (active) setLoadError(errorMessage(failure)) })
    return () => { active = false }
  }, [])

  const coupon = coupons?.find((item) => item.code === code)
  const gross = study.budget.split.patient_cents
  const discount = coupon ? Math.round(gross * coupon.percentage / 100) : 0

  return <form className="est-inline-form" onSubmit={(event) => { event.preventDefault(); run(() => payStudy(study.id, code)) }}>
    <ul className="est-lines">
      {study.budget.split.insurer_cents > 0 && <li><span>Cubre la obra social</span><strong>{money(study.budget.split.insurer_cents)}</strong></li>}
      <li><span>A tu cargo</span><strong>{money(gross)}</strong></li>
      {coupon && <li><span>Cupón {percentLabel(coupon.percentage)}</span><strong>− {money(discount)}</strong></li>}
      <li className="est-total"><span>Total a pagar</span><strong>{money(gross - discount)}</strong></li>
    </ul>
    <div>
      <label htmlFor="est-coupon">Cupón de descuento (opcional)</label>
      {loadError ? <p className="est-help" role="alert">{loadError}</p>
        : <select id="est-coupon" value={code} onChange={(event) => setCode(event.target.value)} disabled={!coupons}>
          <option value="">Sin cupón</option>
          {(coupons || []).map((item) => <option key={item.code} value={item.code}>{item.code} · {percentLabel(item.percentage)}</option>)}
        </select>}
      <p className="est-help">El cupón se aplica sobre lo que pagás vos y no se puede reutilizar.</p>
    </div>
    <p className="est-help" style={{ margin: 0 }}>El pago es simulado: no se cobra ninguna tarjeta real.</p>
    <div className="est-actions"><button type="submit" className="est-primary" disabled={busy}>{busy ? 'Procesando pago...' : 'Pagar'}</button></div>
  </form>
}
