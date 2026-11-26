// Armado de las pruebas de lotes (T05): el mismo de turnos-setup.mjs, con un doble de la API propio.
import { after, afterEach, before, beforeEach } from 'node:test'
import { Window } from 'happy-dom'
import { createServer } from 'vite'
import React, { act } from 'react'
import { AxiosError } from 'axios'

let server, api, setSession, Harness, root, dom
export let container, calls
// Estado del doble; cada prueba lo ajusta antes de renderizar.
export const fake = {}
export const labAdmin = { access_token: 'test-token', role: 'lab_administrator', rol: 'Administrativo' }

// Lotes como los devuelve el back: fechas en hora de Argentina y muestras con el código del estudio, sin paciente.
export const assemblingSet = { id: 4, status: 'assembling', is_urgent: false, created_at: '2026-11-20T10:30:00-03:00', closed_at: null, sample_count: 9 }
export const urgentSet = { id: 3, status: 'closed', is_urgent: true, created_at: '2026-11-18T09:00:00-03:00', closed_at: '2026-11-19T11:15:00-03:00', sample_count: 4 }
export const urgentDetail = { ...urgentSet, samples: [1, 2, 3, 4].map((slot) => ({ slot, sample_id: 20 + slot, study_code: `EST-00002${slot}` })) }
delete urgentDetail.sample_count
const emptyDetail = { id: 5, status: 'assembling', is_urgent: false, created_at: '2026-11-21T08:00:00-03:00', closed_at: null, samples: [] }

function failure(config, status, detail) {
  return new AxiosError(`Request failed with status code ${status}`, 'ERR_BAD_REQUEST', config, null, { status, statusText: '', headers: {}, config, data: { detail } })
}

before(async () => {
  const bootstrap = new Window()
  globalThis.window = bootstrap; globalThis.document = bootstrap.document
  bootstrap.close()
  server = await createServer({ server: { middlewareMode: true, hmr: false }, appType: 'custom' })
  Harness = (await server.ssrLoadModule('/tests/harness.jsx')).default
  api = (await server.ssrLoadModule('/src/services/api.js')).api
  setSession = (await server.ssrLoadModule('/src/services/session.js')).setSession
})
after(async () => { await server?.close() })

beforeEach(async () => {
  dom = new Window({ url: 'http://localhost:5173/' })
  globalThis.window = dom; globalThis.document = dom.document; globalThis.HTMLElement = dom.HTMLElement
  globalThis.IS_REACT_ACT_ENVIRONMENT = true
  container = document.createElement('div'); document.body.append(container)
  root = (await import('react-dom/client')).createRoot(container)
  calls = []
  Object.assign(fake, { networkDown: false, sets: { assembling: [assemblingSet], closed: [urgentSet] }, detail: { 3: urgentDetail, 5: emptyDetail } })
  api.defaults.adapter = async (config) => {
    calls.push({ url: config.url, params: config.params })
    if (fake.networkDown) throw new AxiosError('Network Error', 'ERR_NETWORK', config)
    let data
    if (config.url === '/sample-sets') data = fake.sets[config.params.status] ?? []
    else if (config.url.startsWith('/sample-sets/')) {
      data = fake.detail[config.url.split('/').at(-1)]
      if (!data) throw failure(config, 404, 'El lote no existe.')
    }
    else throw new Error(`Petición inesperada ${config.method} ${config.url}`)
    return { data, status: 200, statusText: 'OK', headers: {}, config }
  }
})
afterEach(async () => { await act(async () => { root.unmount(); setSession(null) }); dom.happyDOM.abort(); dom.close() })

let firstPath
export async function render(path, session = labAdmin) {
  firstPath = path
  await act(async () => { setSession(session); root.render(React.createElement(Harness, { initialEntries: [path] })) })
  await settle()
}
// Navega dentro de la misma app, como un link: la ruta reusa el componente.
export async function go(path) {
  await act(async () => root.render(React.createElement(Harness, { initialEntries: [firstPath], navigateTo: path })))
  await settle()
}
export async function settle() { await act(async () => { await new Promise((resolve) => setTimeout(resolve, 50)) }) }
export async function click(element) { await act(async () => element.click()); await settle() }
export const crumb = () => container.querySelector('.clinical-breadcrumb').textContent
export const tab = (label) => [...container.querySelectorAll('.lotes-tabs button')].find((b) => b.textContent === label)
