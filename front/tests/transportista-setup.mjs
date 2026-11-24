// Armado común de las pruebas de transporte (T04): DOM, sesión y un doble de /transport/* que se comporta como el back.
import assert from 'node:assert/strict'
import { after, afterEach, before, beforeEach, mock } from 'node:test'
import { Window } from 'happy-dom'
import { createServer } from 'vite'
import React, { act } from 'react'
import { AxiosError } from 'axios'

process.env.TZ = 'America/Argentina/Buenos_Aires'

let server, api, createRoot, Harness, setSession, root
export let container, dom, calls
export const fake = {}
export const MONDAY_9 = new Date('2026-11-02T09:00:00-03:00').getTime()
export const labAdmin = { access_token: 'test-token', role: 'lab_administrator', rol: 'Administrativo' }
export const patient = { ...labAdmin, role: 'patient', rol: 'Paciente' }

const center = (id, number) => ({ id, name: `Centro DEMO ${number}`, address: `Calle DEMO ${number}`, city: 'La Plata' })
// Orden de Buenos Aires como la devuelve el back: paradas en la secuencia de la API de recorridos.
export function buenosAiresRoute() {
  return { id: 7, date: '2026-11-02', province_id: 1, province: 'Buenos Aires', status: 'pending', arrived_at: null,
    stops: [{ id: 71, sequence: 1, center: center(13, 3), picked_up_at: null, sample_codes: ['EST-000004'] },
      { id: 72, sequence: 2, center: center(12, 2), picked_up_at: null, sample_codes: ['EST-000003'] },
      { id: 73, sequence: 3, center: center(11, 1), picked_up_at: null, sample_codes: ['EST-000001', 'EST-000002'] }],
    next_stop_id: 71, on_board: [] }
}
export const summary = (route) => ({ id: route.id, date: route.date, province_id: route.province_id, province: route.province,
  status: route.status, arrived_at: route.arrived_at, stops: route.stops.length,
  picked_up: route.stops.filter((stop) => stop.picked_up_at).length })

function failure(config, status, detail) {
  return new AxiosError(`Request failed with status code ${status}`, 'ERR_BAD_REQUEST', config, null,
    { status, statusText: String(status), headers: {}, config, data: { detail } })
}
const ok = (config, data, status = 200) => ({ data, status, statusText: String(status), headers: {}, config })

// Como el back: el retiro sigue el orden fijo y la llegada necesita todas las paradas retiradas.
function pickUp(config, route, stopId) {
  const stop = route.stops.find((item) => item.id === stopId)
  if (!stop) throw failure(config, 404, 'La parada no es de esta orden del día.')
  if (stop.picked_up_at) throw failure(config, 409, 'Este centro ya fue retirado.')
  if (stop.id !== route.next_stop_id) throw failure(config, 409, 'El recorrido es fijo: primero hay que retirar la parada anterior.')
  stop.picked_up_at = '2026-11-02T10:15:00-03:00'
  route.on_board.push(...stop.sample_codes)
  route.next_stop_id = route.stops.find((item) => !item.picked_up_at)?.id ?? null
  return { route_id: route.id, stop_id: stop.id, center: stop.center, picked_up_at: stop.picked_up_at, sample_codes: stop.sample_codes }
}
function arrive(config, route) {
  if (route.status === 'arrived') throw failure(config, 409, 'La llegada de esta orden ya fue registrada.')
  const missing = route.stops.filter((stop) => !stop.picked_up_at).length
  if (missing) throw failure(config, 409, `El recorrido es fijo: faltan retirar ${missing} centros antes de la llegada.`)
  Object.assign(route, { status: 'arrived', arrived_at: '2026-11-02T13:40:00-03:00' })
  const received = route.on_board
  route.on_board = []
  return { route_id: route.id, arrived_at: route.arrived_at, received_codes: received }
}

before(async () => {
  const bootstrap = new Window()
  globalThis.window = bootstrap; globalThis.document = bootstrap.document
  createRoot = (await import('react-dom/client')).createRoot
  bootstrap.close()
  server = await createServer({ server: { middlewareMode: true, hmr: false }, appType: 'custom' })
  Harness = (await server.ssrLoadModule('/tests/harness.jsx')).default
  api = (await server.ssrLoadModule('/src/services/api.js')).api
  setSession = (await server.ssrLoadModule('/src/services/session.js')).setSession
})
after(async () => { await server?.close() })

beforeEach(() => {
  dom = new Window({ url: 'http://localhost:5173/' })
  globalThis.window = dom; globalThis.document = dom.document; globalThis.HTMLElement = dom.HTMLElement
  globalThis.IS_REACT_ACT_ENVIRONMENT = true
  container = document.createElement('div'); document.body.append(container); root = createRoot(container)
  calls = []
  // routes: órdenes ya generadas por fecha; pending: las que generaría el back; route: la de Buenos Aires.
  Object.assign(fake, { networkDown: false, routes: {}, pending: [], generateError: null, route: buenosAiresRoute(), arrivalError: null, myRouteDown: false })
  mock.timers.enable({ apis: ['Date'], now: MONDAY_9 })
  api.defaults.adapter = async (config) => {
    calls.push({ url: config.url, method: config.method, params: config.params, data: config.data && JSON.parse(config.data) })
    if (fake.networkDown) throw new AxiosError('Network Error', 'ERR_NETWORK', config)
    const url = config.url
    if (url.startsWith('/demo/')) throw failure(config, 404, 'Not Found')
    // Como el back: /provinces es del turnero y solo lo puede usar el paciente.
    if (url === '/provinces') throw failure(config, 403, 'Tu rol no permite esta operación.')
    if (url === '/transport/daily-routes' && config.method === 'get') return ok(config, fake.routes[config.params.date] ?? [])
    if (url === '/transport/daily-routes' && config.method === 'post') {
      if (fake.generateError) throw failure(config, fake.generateError[0], fake.generateError[1])
      const { date } = JSON.parse(config.data)
      const created = fake.pending.length > 0
      fake.routes[date] = [...(fake.routes[date] ?? []), ...fake.pending]
      fake.pending = []
      return ok(config, fake.routes[date], created ? 201 : 200)
    }
    if (url === '/transport/my-route') {
      if (fake.myRouteDown) throw failure(config, 500, 'No se pudo cargar la orden del día.')
      const route = fake.route
      if (!route || route.province_id !== Number(config.params.province_id) || route.date !== config.params.date)
        throw failure(config, 404, 'No hay orden del día para esa provincia en esa fecha.')
      return ok(config, structuredClone(route))
    }
    const pickup = url.match(/^\/transport\/daily-routes\/(\d+)\/stops\/(\d+)\/pickup$/)
    if (pickup && config.method === 'post') return ok(config, pickUp(config, fake.route, Number(pickup[2])))
    if (/^\/transport\/daily-routes\/\d+\/arrival$/.test(url) && config.method === 'post') {
      if (fake.arrivalError) throw failure(config, 500, fake.arrivalError)
      return ok(config, arrive(config, fake.route))
    }
    throw new Error(`Petición inesperada ${config.method} ${url}`)
  }
})
afterEach(async () => { await act(async () => { root.unmount(); setSession(null) }); dom.happyDOM.abort(); dom.close(); mock.timers.reset() })

let entries
export async function render(path, session = labAdmin) {
  entries = [path]
  await act(async () => { setSession(session); root.render(React.createElement(Harness, { initialEntries: entries })) })
  await settle()
}
// Navega dentro de la misma app (sin desmontar), como un link que no está en pantalla.
export async function go(path) {
  await act(async () => root.render(React.createElement(Harness, { initialEntries: entries, navigateTo: path })))
  // Sin destino después: si no, el harness vuelve a esta ruta cada vez que la app navega.
  await act(async () => root.render(React.createElement(Harness, { initialEntries: entries })))
  await settle()
}
export async function settle() { await act(async () => { await new Promise((resolve) => setTimeout(resolve, 200)) }) }
export function button(label) {
  const item = [...container.querySelectorAll('button')].find((b) => b.textContent.trim() === label)
  assert.ok(item, `No se encontró botón ${label}`); return item
}
export async function click(element) { await act(async () => element.click()); await settle() }
export async function choose(select, value) {
  await act(async () => {
    Object.getOwnPropertyDescriptor(dom.HTMLSelectElement.prototype, 'value').set.call(select, value)
    select.dispatchEvent(new dom.Event('change', { bubbles: true }))
  })
  await settle()
}
export async function type(input, value) {
  await act(async () => {
    Object.getOwnPropertyDescriptor(dom.HTMLInputElement.prototype, 'value').set.call(input, value)
    input.dispatchEvent(new dom.Event('input', { bubbles: true }))
  })
  await settle()
}
export const text = () => container.querySelector('main').textContent
export const crumb = () => container.querySelector('.clinical-breadcrumb').textContent
