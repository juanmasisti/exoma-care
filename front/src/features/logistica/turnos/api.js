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
