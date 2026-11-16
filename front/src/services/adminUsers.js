import { api } from './api.js'

export async function listManagedUsers() {
  const { data } = await api.get('/admin/users')
  return data
}

export async function createManagedUser(user) {
  const { data } = await api.post('/admin/users', user)
  return data
}
