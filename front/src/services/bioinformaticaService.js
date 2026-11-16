import { api } from './api.js'

export async function fetchPatologiasCatalogo() {
  const { data } = await api.get('/bioinformatica/patologias')
  return data
}

export async function fetchBioinformaticsStudies() {
  const { data } = await api.get('/bioinformatica/estudios')
  return data
}

export async function fetchBioinformaticsHistory(query = '') {
  const { data } = await api.get('/bioinformatica/historial', {
    params: query.trim() ? { q: query.trim() } : undefined,
  })
  return data
}
