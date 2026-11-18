import { api } from './api.js'

const pendingRequests = new Map()

function deduplicateRequest(key, request) {
  const pending = pendingRequests.get(key)
  if (pending) return pending

  const current = request().finally(() => {
    if (pendingRequests.get(key) === current) pendingRequests.delete(key)
  })
  pendingRequests.set(key, current)
  return current
}

export function fetchPatologiasCatalogo() {
  return deduplicateRequest('pathology-catalog', async () => {
    const { data } = await api.get('/bioinformatica/patologias')
    return data
  })
}

export async function fetchBioinformaticsStudies() {
  return deduplicateRequest('studies', async () => {
    const { data } = await api.get('/bioinformatica/estudios')
    return data
  })
}

export async function fetchBioinformaticsHistory(query = '') {
  const normalizedQuery = query.trim()
  return deduplicateRequest(`history:${normalizedQuery}`, async () => {
    const { data } = await api.get('/bioinformatica/historial', {
      params: normalizedQuery ? { q: normalizedQuery } : undefined,
    })
    return data
  })
}
