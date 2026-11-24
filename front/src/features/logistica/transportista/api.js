import { api } from '../../../services/api.js'

// Fecha de hoy (YYYY-MM-DD) en la zona del navegador: la orden es "de cada mañana".
export function today() {
  const now = new Date()
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`
}

// Devuelve también el status: 201 si generó alguna orden, 200 si ya estaban todas.
export async function generateDailyRoutes(date) {
  const response = await api.post('/transport/daily-routes', { date })
  return { created: response.status === 201, routes: response.data }
}
export async function listDailyRoutes(date) {
  return (await api.get('/transport/daily-routes', { params: { date } })).data
}

export const ROUTE_STATUS = { pending: 'Pendiente', arrived: 'Recibida en el laboratorio central' }
