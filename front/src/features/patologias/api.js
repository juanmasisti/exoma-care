import { api } from '../../services/api.js'

export async function listPathologies() {
  return (await api.get('/pathologies')).data
}
export async function searchSymptoms(query, signal) {
  return (await api.get('/symptoms', { params: { q: query }, signal })).data
}
export async function savePathology(id, body) {
  return (await (id
    ? api.put(`/pathologies/${id}`, body)
    : api.post('/pathologies', body))).data
}
export async function validateSuspicion(id, symptomIds) {
  return (await api.post(`/pathologies/${id}/validate-suspicion`, { symptom_ids: symptomIds })).data
}
