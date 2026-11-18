import { api } from '../../services/api.js'

const BASE = '/solicitudes-estudio'

// --- Solicitudes (EC-10) ---
export async function getPathologyCatalog() { return (await api.get(`${BASE}/catalogo`)).data }
export async function searchGenes(query) { return (await api.get(`${BASE}/genes`, { params: { q: query } })).data }
export async function createStudyRequest(payload) { return (await api.post(BASE, payload)).data }
export async function listStudyRequests() { return (await api.get(BASE)).data }
export async function getStudyRequest(studyId) { return (await api.get(`${BASE}/${studyId}`)).data }

async function downloadStudyFile(studyId, format, mediaType) {
  const response = await api.get(
    `/bioinformatica/estudios/${studyId}/resultado.${format}`,
    { responseType: 'blob' },
  )
  const blob = new Blob([response.data], { type: mediaType })
  const url = window.URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `estudio-${studyId}-resultado.${format}`
  document.body.appendChild(link)
  link.click()
  link.remove()
  window.URL.revokeObjectURL(url)
}

export function downloadStudyResult(studyId) {
  return downloadStudyFile(studyId, 'pdf', 'application/pdf')
}

export function downloadStudyResultSvg(studyId) {
  return downloadStudyFile(studyId, 'svg', 'image/svg+xml')
}

// --- Presupuesto (EC-11) ---
// Emitir devuelve solo el presupuesto: se vuelve a leer el estudio para que la pantalla reciba el detalle completo.
export async function issueBudget(studyId) {
  await api.post(`${BASE}/${studyId}/presupuesto`)
  return getStudyRequest(studyId)
}

// --- Modalidad de pago, cobertura y pago (EC-13) ---
export async function listInsurers(search) {
  return (await api.get(`${BASE}/obras-sociales`, { params: search ? { buscar: search } : {} })).data
}
export async function choosePaymentMode(studyId, mode, insurerId) {
  return (await api.post(`${BASE}/${studyId}/modalidad-pago`, { mode, obra_social_id: insurerId || null })).data
}
export async function authorizeCoverage(studyId, percent) {
  return (await api.post(`${BASE}/${studyId}/cobertura/autorizar`, percent === null || percent === undefined ? {} : { porcentaje: percent })).data
}
export async function rejectCoverage(studyId, reason) {
  return (await api.post(`${BASE}/${studyId}/cobertura/rechazar`, { motivo: reason })).data
}
// El PDF viaja como cuerpo crudo (application/pdf), sin multipart.
export async function submitDemand(studyId, file) {
  return (await api.post(`${BASE}/${studyId}/cobertura/demanda`, file, {
    params: { filename: file.name },
    headers: { 'Content-Type': 'application/pdf' },
    timeout: 60000,
  })).data
}
export async function payStudy(studyId, couponCode) {
  return (await api.post(`${BASE}/${studyId}/pago`, couponCode ? { coupon_code: couponCode } : {})).data
}

// --- Cupones (EC-12) ---
export async function listCoupons(status) { return (await api.get('/cupones', { params: status ? { estado: status } : {} })).data }
export async function listCouponPhysicians() { return (await api.get('/cupones/medicos')).data }
export async function generateCoupons(quantity, percent) {
  return (await api.post('/cupones/lote', { cantidad: quantity, porcentaje_descuento: percent })).data
}
export async function assignCouponToPhysician(code, physicianId) {
  return (await api.post(`/cupones/${encodeURIComponent(code)}/asignar-medico`, { medico_id: physicianId })).data
}
export async function assignCouponToPatient(code, patientId) {
  return (await api.post(`/cupones/${encodeURIComponent(code)}/asignar-paciente`, { patient_id: patientId })).data
}
