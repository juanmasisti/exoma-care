import { api } from '../../services/api.js'
const base = '/clinical-integrations'
export const getGeneticCatalog = async () => (await api.get(`${base}/apigen/pathologies`)).data
export const getCDSSCatalog = async () => (await api.get(`${base}/cdss/pathologies`, { timeout: 70000 })).data
export const getGenes = async (q) => (await api.get(`${base}/apigen/genes`, { params: { q } })).data
export const createGeneticPathology = async (body) => (await api.post(`${base}/apigen/pathologies`, body)).data
export const linkPathology = async (id, body) => (await api.put(`${base}/pathologies/${id}/identity`, body, { timeout: 70000 })).data
export const getCDSSAdvice = async (symptom_ids, signal) => (await api.post(`${base}/cdss/advice`, { symptom_ids }, { signal, timeout: 70000 })).data
export const importCDSSDraft = async (code) => (await api.post(`${base}/cdss/pathologies/${encodeURIComponent(code)}/draft`, null, { timeout: 70000 })).data
