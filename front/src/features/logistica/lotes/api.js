import { api } from '../../../services/api.js'

export async function listSampleSets(status) {
  return (await api.get('/sample-sets', { params: { status } })).data
}
export async function getSampleSet(sampleSetId) {
  return (await api.get(`/sample-sets/${sampleSetId}`)).data
}
