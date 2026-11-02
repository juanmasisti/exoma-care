import { api } from '../../../services/api.js'

export async function listProvinces() { return (await api.get('/provinces')).data }
export async function listCenters(provinceId) {
  return (await api.get('/extraction-centers', { params: { province_id: provinceId } })).data
}
export async function getSlots(centerId, date) {
  return (await api.get(`/extraction-centers/${centerId}/slots`, { params: { date } })).data
}
