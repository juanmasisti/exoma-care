import { api } from '../../services/api.js'

export async function searchTerminology(query, signal) {
  return (await api.get('/terminology/symptoms', { params: { q: query, limit: 10 }, signal })).data
}
export async function importTerminology(selectionToken, signal) {
  return (await api.post('/terminology/symptoms/import', { selection_token: selectionToken }, { signal })).data
}
