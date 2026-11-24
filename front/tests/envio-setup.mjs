// Armado de las pruebas del envío del lote (T06): DOM, sesión del administrativo y doble de /shipments.
import assert from 'node:assert/strict'
import { after, afterEach, before, beforeEach } from 'node:test'
import { Window } from 'happy-dom'
import { createServer } from 'vite'
import React, { act } from 'react'
import { AxiosError } from 'axios'

let server, api, setSession, Harness, EnvioLote, createRoot, root
export let container, dom, calls
export const labAdmin = { access_token: 'test-token', role: 'lab_administrator', rol: 'Administrativo' }
export const PICKUP_AT = '2026-12-02T10:00:00-03:00'
// Estado del doble: el envío del lote 1 y los errores que cada prueba quiera simular.
export const fake = {}

export function shipment(status = 'closed', overrides = {}) {
  return { id: 1, status, has_csv: true, has_authorization: true, pickup_at: null, courier_pickup_id: null, ...overrides }
}

export function failure(config, status, detail) {
  return new AxiosError(`Request failed with status code ${status}`, 'ERR_BAD_REQUEST', config, null,
    { status, statusText: '', headers: {}, config, data: { detail } })
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
  EnvioLote = (await server.ssrLoadModule('/src/features/logistica/lotes/EnvioLote.jsx')).default
})
after(async () => { await server?.close() })

beforeEach(() => {
  dom = new Window({ url: 'http://localhost:5173/' })
  globalThis.window = dom; globalThis.document = dom.document; globalThis.HTMLElement = dom.HTMLElement
  globalThis.IS_REACT_ACT_ENVIRONMENT = true
  container = document.createElement('div'); document.body.append(container); root = createRoot(container)
  calls = []
  Object.assign(fake, { shipment: shipment(), loadDown: false, reject: null, afterRefresh: null })
  api.defaults.adapter = async (config) => {
    calls.push({ url: config.url, method: config.method, data: config.data && JSON.parse(config.data),
      responseType: config.responseType, authorization: config.headers?.Authorization })
    const ok = (data) => ({ data, status: 200, statusText: 'OK', headers: {}, config })
    // `reject`: {url, status, detail} para que esa petición falle como el back.
    if (fake.reject?.url === config.url) {
      const { status, detail } = fake.reject
      if (config.responseType === 'blob') {
        const body = new Blob([JSON.stringify({ detail })], { type: 'application/json' })
        throw new AxiosError('Request failed', 'ERR_BAD_REQUEST', config, null, { status, statusText: '', headers: {}, config, data: body })
      }
      throw failure(config, status, detail)
    }
    if (config.url === '/shipments/1' && config.method === 'get') {
      if (fake.loadDown) throw new AxiosError('Network Error', 'ERR_NETWORK', config)
      return ok(fake.shipment)
    }
    if (config.url === '/shipments/1/authorization') return ok(fake.shipment = { ...fake.shipment, has_csv: true, has_authorization: true })
    if (config.url === '/shipments/1/pickup') {
      return ok(fake.shipment = { ...fake.shipment, status: 'awaiting_pickup', pickup_at: PICKUP_AT, courier_pickup_id: 'uuid-demo' })
    }
    if (config.url === '/shipments/1/refresh') return ok(fake.shipment = { ...fake.shipment, status: fake.afterRefresh ?? fake.shipment.status })
    if (config.url === '/shipments/1/csv') return ok(new Blob(['dni,apellido'], { type: 'text/csv' }))
    if (config.url === '/shipments/1/authorization.pdf') return ok(new Blob(['%PDF-DEMO'], { type: 'application/pdf' }))
    // Detalle del lote (T05): lo carga antes de montar el envío. Sigue el estado del envío del doble.
    if (config.url === '/sample-sets/1') {
      const { status } = fake.shipment
      return ok({ id: 1, status, is_urgent: false, created_at: '2026-11-20T10:00:00-03:00',
        closed_at: status === 'assembling' ? null : '2026-11-21T11:00:00-03:00',
        samples: Array.from({ length: 10 }, (_, index) => ({ slot: index + 1, sample_id: 11 + index, study_code: `EST-0000${11 + index}` })) })
    }
    throw failure(config, 404, 'Not Found')
  }
})
afterEach(async () => { await act(async () => { root.unmount(); setSession(null) }); dom.happyDOM.abort(); dom.close() })

export async function render(path = '/administrativo/lotes/1') {
  await act(async () => { setSession(labAdmin); root.render(React.createElement(Harness, { initialEntries: [path] })) })
  await settle()
}
// Solo el bloque del envío, para ver qué le avisa al detalle del lote con onChange.
export async function renderAlone(onChange) {
  await act(async () => { setSession(labAdmin); root.render(React.createElement(EnvioLote, { session: labAdmin, sampleSetId: '1', onChange })) })
  await settle()
}
export async function settle() { await act(async () => { await new Promise((resolve) => setTimeout(resolve, 50)) }) }
export const section = () => container.querySelector('section[aria-label="Envío del lote"]')
export function button(label) {
  const item = [...section().querySelectorAll('button')].find((b) => b.textContent.trim() === label)
  assert.ok(item, `No se encontró el botón ${label}`); return item
}
export const hasButton = (label) => [...section().querySelectorAll('button')].some((b) => b.textContent.trim() === label)
export async function click(label) { await act(async () => button(label).click()); await settle() }
export async function type(input, value) {
  await act(async () => {
    Object.getOwnPropertyDescriptor(dom.HTMLInputElement.prototype, 'value').set.call(input, value)
    input.dispatchEvent(new dom.Event('input', { bubbles: true }))
  })
}
