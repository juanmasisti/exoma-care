import { api } from '../../services/api.js'

export async function getFamily(patientId) { return (await api.get(`/patients/${patientId}/family`)).data }
export async function saveFamily(patientId, body) { return (await api.put(`/patients/${patientId}/family`, body)).data }
export async function getFamilyHistory(patientId) { return (await api.get(`/patients/${patientId}/family/history`)).data }

export async function getFamiliograms(patientId) { return (await api.get(`/patients/${patientId}/familiogram`)).data }
export async function getRelationships(patientId) { return (await api.get(`/patients/${patientId}/familiogram/relationships`)).data }
export async function generateFamiliogram(patientId, body) { return (await api.post(`/patients/${patientId}/familiogram`, body)).data }
export async function getFamiliogramFile(patientId, documentId, format) { return (await api.get(`/patients/${patientId}/familiogram/${documentId}/${format}`, { responseType: 'blob' })).data }
export async function getPatientVersion(patientId) { return (await api.get(`/patients/${patientId}`)).data.version }
