import { api } from '../../services/api.js'

export async function getFamily(patientId) { return (await api.get(`/patients/${patientId}/family`)).data }
export async function saveFamily(patientId, body) { return (await api.put(`/patients/${patientId}/family`, body)).data }
export async function getFamilyHistory(patientId) { return (await api.get(`/patients/${patientId}/family/history`)).data }
