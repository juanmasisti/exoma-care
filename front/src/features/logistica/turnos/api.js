import { api } from '../../../services/api.js'

export async function listProvinces() { return (await api.get('/provinces')).data }
export async function listCenters(provinceId) {
  return (await api.get('/extraction-centers', { params: { province_id: provinceId } })).data
}
export async function getSlots(centerId, date) {
  return (await api.get(`/extraction-centers/${centerId}/slots`, { params: { date } })).data
}
export async function bookAppointment(studyId, centerId, startsAt) {
  return (await api.post('/appointments', { study_id: studyId, center_id: centerId, starts_at: startsAt })).data
}
export async function getStudyAppointment(studyId) {
  return (await api.get(`/studies/${studyId}/appointment`)).data
}
export async function cancelAppointment(appointmentId) {
  await api.delete(`/appointments/${appointmentId}`)
}
export async function listMyAppointments() {
  return (await api.get('/appointments/mine')).data
}
export async function listEligibleStudies() {
  return (await api.get('/appointments/eligible-studies')).data
}
// Por axios y no con un link: el token viaja en el header Authorization.
export async function downloadAppointmentDocument(appointmentId, kind) {
  try {
    return (await api.get(`/appointments/${appointmentId}/documents/${kind}`, { responseType: 'blob' })).data
  } catch (failure) {
    // Con responseType blob el error también llega como Blob: se lee para que errorMessage muestre el detail.
    const body = failure.response?.data
    if (body instanceof Blob) {
      try { failure.response.data = JSON.parse(await body.text()) } catch { /* sin detail: queda el mensaje genérico */ }
    }
    throw failure
  }
}
