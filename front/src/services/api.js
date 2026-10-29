import axios from 'axios'
import { getSession, setSession } from './session.js'

export const api = axios.create({ baseURL: '/api', timeout: 15000 })
api.interceptors.request.use((config) => {
  const token = getSession()?.access_token
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})
api.interceptors.response.use((response) => response, (error) => {
  if (error.response?.status === 401) setSession(null)
  return Promise.reject(error)
})

export function errorMessage(error) {
  const detail = error.response?.data?.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) return 'Revisá los datos ingresados y los campos obligatorios.'
  return 'No se pudo completar la operación. Revisá la conexión e intentá nuevamente.'
}

export async function login(email, password) {
  const { data } = await api.post('/auth/login', { email, password })
  setSession(data)
  return data
}
