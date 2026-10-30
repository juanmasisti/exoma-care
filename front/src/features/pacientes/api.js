import { api } from '../../services/api.js'

export async function listPatients(query, offset, signal) {
  return (await api.get('/patients', { params: { q: query, offset, limit: 20 }, signal })).data
}
export async function getPatient(id) { return (await api.get(`/patients/${id}`)).data }
export async function getPatientHistory(id) { return (await api.get(`/patients/${id}/history`)).data }
export async function evaluatePatient(body) { return (await api.post('/patients/validate', body)).data }
export async function savePatient(id, body) {
  return (await (id ? api.put(`/patients/${id}`, body) : api.post('/patients', body))).data
}
