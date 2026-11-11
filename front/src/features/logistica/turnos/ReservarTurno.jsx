import { useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { ArrowLeft, ArrowRight, ChevronLeft, ChevronRight, MapPin } from 'lucide-react'
import ClinicalLayout from '../../../components/layout/ClinicalLayout.jsx'
import { errorMessage } from '../../../services/api.js'
import { bookAppointment, getSlots, listCenters, listProvinces } from './api.js'
import CentersMap from './CentersMap.jsx'
// Por la paginación, que usa las mismas clases que PatientsList (patients-pagination).
import '../../pacientes/patients.css'
import './turnos.css'

const WEEKDAYS = [['Lunes', 'Lun'], ['Martes', 'Mar'], ['Miércoles', 'Mié'], ['Jueves', 'Jue'], ['Viernes', 'Vie'], ['Sábado', 'Sáb'], ['Domingo', 'Dom']]

// AAAA-MM-DD con la fecha local. No usar toISOString(): pasa a UTC y, para la fecha de hoy después de las 21, da el día siguiente.
function dateKey(year, month, day) {
  return `${year}-${String(month + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`
}

export default function ReservarTurno({ session }) {
  const navigate = useNavigate()
  // PROVISORIO: hasta que estudios ofrezca la lista de estudios del paciente, llega por ?estudio=ID.
  const studyParam = Number(useSearchParams()[0].get('estudio'))
  const studyId = Number.isInteger(studyParam) && studyParam > 0 ? studyParam : null
  const [booking, setBooking] = useState(false)
  const [bookingError, setBookingError] = useState('')
  const [provinces, setProvinces] = useState(null)
  const [provincesError, setProvincesError] = useState('')
  const [provincesRetry, setProvincesRetry] = useState(0)
  const [provinceId, setProvinceId] = useState('')
  const [centers, setCenters] = useState(null)
  const [centersError, setCentersError] = useState('')
  const [centersRetry, setCentersRetry] = useState(0)
  const [centerId, setCenterId] = useState(null)
  const [pageSize, setPageSize] = useState(8) // 0 = todos
  const [page, setPage] = useState(0)
  // Se actualiza al elegir centro o día, para que pasada la medianoche el día anterior quede deshabilitado.
  const [today, setToday] = useState(() => new Date())
  const [month, setMonth] = useState(() => ({ year: today.getFullYear(), month: today.getMonth() }))
  const [day, setDay] = useState(null)
  const [slots, setSlots] = useState(null)
  const [slotsError, setSlotsError] = useState('')
  const [slotsRetry, setSlotsRetry] = useState(0)
  const [slot, setSlot] = useState(null)

  useEffect(() => {
    let active = true
    listProvinces().then((data) => { if (active) setProvinces(data) })
      .catch((failure) => { if (active) setProvincesError(errorMessage(failure)) })
    return () => { active = false }
  }, [provincesRetry])

  useEffect(() => {
    if (!provinceId) return
    let active = true
    // Orden natural: "Centro 2" antes que "Centro 10".
    listCenters(provinceId).then((data) => { if (active) setCenters(data.toSorted((a, b) => a.name.localeCompare(b.name, 'es', { numeric: true }))) })
      .catch((failure) => { if (active) setCentersError(errorMessage(failure)) })
    return () => { active = false }
  }, [provinceId, centersRetry])

  useEffect(() => {
    if (!centerId || !day) return
    let active = true
    getSlots(centerId, day).then((data) => { if (active) setSlots(data) })
      .catch((failure) => { if (active) setSlotsError(errorMessage(failure)) })
    return () => { active = false }
  }, [centerId, day, slotsRetry])

  function chooseDay(key) {
    setToday(new Date()); setDay(key); setSlots(null); setSlotsError(''); setSlot(null)
    // La misma fecha no cambia las dependencias del efecto: pedir recarga explícita.
    if (key && key === day) setSlotsRetry((n) => n + 1)
  }
  function chooseCenter(id) { setCenterId(id); chooseDay(null) }
  function chooseProvince(id) { setProvinceId(id); setCenters(null); setCentersError(''); setPage(0); chooseCenter(null) }
  function chooseFromMap(id) {
    if (pageSize) setPage(Math.floor(centers.findIndex((item) => item.id === id) / pageSize))
    chooseCenter(id)
  }
  function chooseSlot(starts) { setSlot(starts); setBookingError('') }
  async function confirm() {
    setBooking(true); setBookingError('')
    try {
      await bookAppointment(studyId, centerId, slot)
      navigate(`/paciente/estudios/${studyId}/turno`)
    } catch (failure) {
      setBooking(false)
      setBookingError(errorMessage(failure))
      // Horario tomado por otro: se vuelven a pedir los horarios del día para que desaparezca.
      if (failure.response?.status === 409) chooseDay(day)
    }
  }
  function moveMonth(step) { const first = new Date(month.year, month.month + step, 1); setMonth({ year: first.getFullYear(), month: first.getMonth() }) }

  const todayKey = dateKey(today.getFullYear(), today.getMonth(), today.getDate())
  const isCurrentMonth = month.year === today.getFullYear() && month.month === today.getMonth()
  const daysInMonth = new Date(month.year, month.month + 1, 0).getDate()
  const leadingBlanks = (new Date(month.year, month.month, 1).getDay() + 6) % 7
  const monthName = new Date(month.year, month.month, 1).toLocaleDateString('es-AR', { month: 'long', year: 'numeric' })
  const monthLabel = monthName[0].toUpperCase() + monthName.slice(1)
  const center = centers?.find((item) => item.id === centerId)
  const total = centers?.length ?? 0
  const limit = pageSize || total
  const offset = page * limit
  const [year, monthNumber, dayNumber] = day ? day.split('-').map(Number) : []
  const dayLabel = day && new Date(year, monthNumber - 1, dayNumber).toLocaleDateString('es-AR', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' })

  return <ClinicalLayout session={session}><section className="turnos-page">
    <header className="turnos-header"><h1>Reservá tu turno de extracción</h1><p>Elegí un centro de extracción y un horario libre.</p></header>

    <div className="turnos-layout"><div className="turnos-steps">
    <section className="turnos-card" aria-labelledby="turnos-centers-title">
      <h2 id="turnos-centers-title">1. Centro de extracción</h2>
      {provincesError ? <div role="alert" className="turnos-error"><p>{provincesError}</p><button type="button" onClick={() => { setProvincesError(''); setProvincesRetry((n) => n + 1) }}>Reintentar</button></div>
        : !provinces ? <p role="status" className="turnos-loading">Cargando provincias...</p>
          : <><label htmlFor="turnos-province">Provincia</label>
            <select id="turnos-province" value={provinceId} onChange={(event) => chooseProvince(event.target.value)}>
              <option value="">Elegí una provincia</option>
              {provinces.map((province) => <option key={province.id} value={province.id}>{province.name} ({province.active_centers} {province.active_centers === 1 ? 'centro' : 'centros'})</option>)}
            </select></>}

      {centers?.length > 0 && <CentersMap centers={centers} centerId={centerId} onChoose={chooseFromMap} />}
      {provinceId && (centersError ? <div role="alert" className="turnos-error"><p>{centersError}</p><button type="button" onClick={() => { setCentersError(''); setCentersRetry((n) => n + 1) }}>Reintentar</button></div>
        : !centers ? <p role="status" className="turnos-loading">Cargando centros...</p>
          : centers.length === 0 ? <p className="turnos-empty">No hay centros activos en esta provincia.</p>
            : <>
              {total > 8 && <div className="turnos-page-size"><label htmlFor="turnos-page-size">Centros por página</label>
                <select id="turnos-page-size" value={pageSize} onChange={(event) => { setPageSize(Number(event.target.value)); setPage(0) }}>
                  <option value={8}>8</option><option value={12}>12</option><option value={0}>Todos</option>
                </select></div>}
              <ul className="turnos-centers">{centers.slice(offset, offset + limit).map((item) => <li key={item.id}>
                <button type="button" className="turnos-center" aria-pressed={item.id === centerId} onClick={() => chooseCenter(item.id)}>
                  <MapPin size={18} aria-hidden="true" /><span><strong>{item.name}</strong><small>{item.address}</small></span>
                </button></li>)}</ul>
              {total > limit && <div className="patients-pagination"><span>{offset + 1}–{Math.min(offset + limit, total)} de {total} centros</span><div><button type="button" disabled={offset === 0} onClick={() => setPage(page - 1)}><ArrowLeft size={14} aria-hidden="true" />Anterior</button><button type="button" disabled={offset + limit >= total} onClick={() => setPage(page + 1)}>Siguiente<ArrowRight size={14} aria-hidden="true" /></button></div></div>}
            </>)}
    </section>

    {center && <section className="turnos-card" aria-labelledby="turnos-date-title">
      <h2 id="turnos-date-title">2. Elegí una fecha</h2>
      <div className="turnos-calendar-header">
        <button type="button" aria-label="Mes anterior" disabled={isCurrentMonth} onClick={() => moveMonth(-1)}><ChevronLeft size={16} aria-hidden="true" /></button>
        <strong>{monthLabel}</strong>
        <button type="button" aria-label="Mes siguiente" onClick={() => moveMonth(1)}><ChevronRight size={16} aria-hidden="true" /></button>
      </div>
      <div className="turnos-calendar" role="group" aria-label="Días del mes">
        {WEEKDAYS.map(([long, short]) => <span key={long} className="turnos-weekday" aria-hidden="true"><span className="turnos-weekday-long">{long}</span><span className="turnos-weekday-short">{short}</span></span>)}
        {Array.from({ length: leadingBlanks }, (_, index) => <span key={`blank-${index}`} />)}
        {Array.from({ length: daysInMonth }, (_, index) => {
          const number = index + 1
          const key = dateKey(month.year, month.month, number)
          const date = new Date(month.year, month.month, number)
          const weekday = date.getDay()
          const disabled = weekday === 0 || weekday === 6 || key < todayKey
          return <button key={key} type="button" className="turnos-day" data-date={key} disabled={disabled} aria-pressed={key === day}
            aria-label={date.toLocaleDateString('es-AR', { weekday: 'long', day: 'numeric', month: 'long' })} onClick={() => chooseDay(key)}>{number}</button>
        })}
      </div>
    </section>}

    {day && <section className="turnos-card" aria-labelledby="turnos-slots-title">
      <h2 id="turnos-slots-title">3. Elegí un horario</h2>
      <div aria-live="polite">{slotsError ? <div role="alert" className="turnos-error"><p>{slotsError}</p><button type="button" onClick={() => { setSlotsError(''); setSlotsRetry((n) => n + 1) }}>Reintentar</button></div>
        : !slots ? <p role="status" className="turnos-loading">Cargando horarios...</p>
          : slots.holiday ? <p className="turnos-empty">Feriado: {slots.holiday}</p>
            : slots.slots.length === 0 ? <p className="turnos-empty">No hay turnos libres.</p>
              : <div className="turnos-slots" role="group" aria-label="Horarios libres">{slots.slots.map((starts) => <button key={starts} type="button" className="turnos-slot" aria-pressed={starts === slot} onClick={() => chooseSlot(starts)}>{starts.slice(11, 16)}</button>)}</div>}</div>
    </section>}

    </div>

    <aside className="turnos-summary turnos-card" aria-labelledby="turnos-summary-title">
      <h2 id="turnos-summary-title">Tu selección</h2>
      <dl>
        <dt>Centro</dt><dd>{center ? <>{center.name}<small>{center.address}</small></> : 'Sin elegir'}</dd>
        <dt>Fecha</dt><dd>{dayLabel || 'Sin elegir'}</dd>
        {/* La hora sale del ISO del back, que ya viene en hora de Argentina; así no depende de la zona del navegador. */}
        <dt>Hora</dt><dd>{slot ? `${slot.slice(11, 16)} h` : 'Sin elegir'}</dd>
      </dl>
      {bookingError && <div role="alert" className="turnos-error turnos-booking-error"><p>{bookingError}</p></div>}
      <button type="button" className="turnos-primary" disabled={!studyId || !slot || booking} onClick={confirm}
        aria-describedby={studyId ? undefined : 'turnos-confirm-note'}>{booking ? 'Reservando...' : 'Confirmar turno'}</button>
      {!studyId && <p id="turnos-confirm-note">Elegí el estudio para el que querés sacar turno.</p>}
    </aside>
    </div>
  </section></ClinicalLayout>
}
