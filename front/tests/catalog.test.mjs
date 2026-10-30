import assert from 'node:assert/strict'
import { after, afterEach, before, beforeEach, test } from 'node:test'
import { Window } from 'happy-dom'
import { createServer } from 'vite'
import React, { act } from 'react'
import { AxiosError } from 'axios'

let server, Harness, api, setSession, root, container, dom, createRoot
let pathologies, requests, duplicate
const terms = [1, 2, 3, 4].map((id) => ({ id, code: `DEMO-${id}`, label: `Síntoma demo ${id}`, code_system: 'DEMO' }))
const manager = { access_token: 'test-token', role: 'medical_manager', rol: 'Gerente' }
const physician = { access_token: 'test-token', role: 'treating_physician', rol: 'Médico' }
const basePathology = () => ({ id: 1, name: 'Patología demo', cardinal_symptom: terms[0], secondary_symptoms: [terms[1], terms[2]] })

before(async () => {
  const bootstrap = new Window()
  globalThis.window = bootstrap
  globalThis.document = bootstrap.document
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
  globalThis.window = dom
  globalThis.document = dom.document
  globalThis.HTMLElement = dom.HTMLElement
  globalThis.IS_REACT_ACT_ENVIRONMENT = true
  container = document.createElement('div')
  document.body.append(container)
  root = createRoot(container)
  pathologies = []
  requests = []
  duplicate = false
  api.defaults.adapter = async (config) => {
    const body = typeof config.data === 'string' ? JSON.parse(config.data) : config.data
    requests.push({ method: config.method, url: config.url, body })
    let data
    if (config.url === '/symptoms') {
      const query = config.params?.q?.toLowerCase() ?? ''
      data = terms.filter((s) => `${s.label} ${s.code}`.toLowerCase().includes(query))
    } else if (config.url === '/pathologies' && config.method === 'get') data = [...pathologies]
    else if (config.url.endsWith('/validate-suspicion')) {
      const selected = new Set(body.symptom_ids)
      const secondary = [2, 3].filter((id) => selected.has(id))
      data = { valid: selected.has(1) || secondary.length >= 2, criterion: selected.has(1) ? 'cardinal' : secondary.length >= 2 ? 'two_secondary' : 'insufficient_symptoms', matched_secondary_ids: secondary }
    } else if (['post', 'put'].includes(config.method)) {
      if (duplicate) throw new AxiosError('duplicate', 'ERR_BAD_REQUEST', config, null, { status: 409, data: { detail: 'Ya existe una patología con ese nombre.' } })
      const id = config.method === 'put' ? Number(config.url.split('/').at(-1)) : 1
      data = { id, name: body.name, cardinal_symptom: terms.find((s) => s.id === body.cardinal_symptom_id), secondary_symptoms: body.secondary_symptom_ids.map((id) => terms.find((s) => s.id === id)) }
      pathologies = [...pathologies.filter((p) => p.id !== id), data]
    } else throw new Error(`Petición inesperada: ${config.method} ${config.url}`)
    return { data, status: 200, statusText: 'OK', headers: {}, config }
  }
})

afterEach(async () => {
  await act(async () => { root.unmount(); setSession(null) })
  dom.happyDOM.abort()
  dom.close()
})

async function render(session = manager) {
  await act(async () => { setSession(session); root.render(React.createElement(Harness)) })
  await settle()
}
async function settle() { await act(async () => { await new Promise((resolve) => setTimeout(resolve, 310)) }) }
function button(name) {
  const result = [...container.querySelectorAll('button')].find((b) => (b.getAttribute('aria-label') ?? b.textContent.trim()) === name)
  assert.ok(result, `No se encontró botón ${name}`)
  return result
}
function control(labelText) {
  const label = [...container.querySelectorAll('label')].find((el) => el.textContent.trim().replace(/ \*$/, '') === labelText)
  assert.ok(label, `No se encontró etiqueta ${labelText}`)
  return document.getElementById(label.htmlFor)
}
async function click(element) { await act(async () => element.click()) }
async function change(element, value) {
  await act(async () => {
    // El setter nativo simula la edición del usuario, sin modificar el estado de React directamente.
    const prototype = element.tagName === 'SELECT' ? dom.HTMLSelectElement.prototype : dom.HTMLInputElement.prototype
    Object.getOwnPropertyDescriptor(prototype, 'value').set.call(element, value)
    element.dispatchEvent(new dom.Event(element.tagName === 'SELECT' ? 'change' : 'input', { bubbles: true }))
  })
}
async function selectPathology() { await click(button('Patología demo')); await settle() }

test('el gerente crea una patología con cardinal y secundarios sin duplicados', async () => {
  await render()
  assert.equal(button('Guardar patología').disabled, true)
  await change(control('Nombre de la patología'), 'Nueva demo')
  await change(control('Seleccionar síntoma cardinal'), '1')
  const secondary = control('Seleccionar síntomas secundarios')
  assert.equal([...secondary.options].some((o) => o.value === '1'), false)
  await change(secondary, '2')
  await change(control('Seleccionar síntomas secundarios'), '3')
  assert.equal([...control('Seleccionar síntomas secundarios').options].some((o) => o.value === '2'), false)
  await click(button('Guardar patología'))
  assert.match(container.textContent, /Patología guardada correctamente/)
  const request = requests.find((r) => r.method === 'post' && r.url === '/pathologies')
  assert.deepEqual(request.body, { name: 'Nueva demo', cardinal_symptom_id: 1, secondary_symptom_ids: [2, 3] })
  assert.equal(button('Nueva demo').getAttribute('aria-current'), 'true')
})

test('la edición conserva el ID y reemplaza la configuración', async () => {
  pathologies = [basePathology()]
  await render(); await selectPathology()
  await change(control('Nombre de la patología'), 'Demo editada')
  await change(control('Seleccionar síntoma cardinal'), '2')
  await click(button('Guardar patología'))
  const request = requests.find((r) => r.method === 'put')
  assert.equal(request.url, '/pathologies/1')
  assert.equal(request.body.name, 'Demo editada')
  assert.equal(request.body.cardinal_symptom_id, 2)
  assert.deepEqual(request.body.secondary_symptom_ids, [3])
})

test('el médico consulta y valida pero no ve acciones de mantenimiento', async () => {
  pathologies = [basePathology()]
  await render(physician); await selectPathology()
  assert.equal([...container.querySelectorAll('button')].some((b) => /Guardar patología|Nueva patología/.test(b.textContent)), false)
  await change(control('Seleccionar síntomas presentes'), '2')
  await change(control('Seleccionar síntomas presentes'), '3')
  await click(button('Validar sospecha'))
  assert.match(container.textContent, /Sospecha consistente/)
  assert.match(container.textContent, /dos síntomas secundarios distintos/)
  assert.deepEqual(requests.find((r) => r.url.endsWith('/validate-suspicion')).body.symptom_ids, [2, 3])
})

test('una sospecha insuficiente muestra el motivo sin dar un diagnóstico', async () => {
  pathologies = [basePathology()]
  await render(physician); await selectPathology()
  await change(control('Seleccionar síntomas presentes'), '2')
  await click(button('Validar sospecha'))
  assert.match(container.textContent, /Criterio no cumplido/)
  assert.match(container.textContent, /No establece un diagnóstico/)
})

test('el conflicto de nombre se informa y conserva lo escrito', async () => {
  duplicate = true
  await render()
  await change(control('Nombre de la patología'), 'Repetida')
  await change(control('Seleccionar síntoma cardinal'), '1')
  await click(button('Guardar patología'))
  assert.match(container.querySelector('[role="alert"]').textContent, /Ya existe/)
  assert.equal(control('Nombre de la patología').value, 'Repetida')
  assert.equal(button('Guardar patología').disabled, false)
})

test('sin sesión se redirige al login y no se consulta el catálogo', async () => {
  await render(null)
  assert.match(container.textContent, /Iniciar sesión/)
  assert.equal(requests.length, 0)
})

test('un paciente no ve ni consulta el catálogo', async () => {
  await render({ ...manager, role: 'patient', rol: 'Paciente' })
  assert.match(container.textContent, /portal de tu perfil todavía no está disponible/)
  assert.equal(requests.length, 0)
})


test('buscar por nombre filtra el listado y permite recuperar los resultados', async () => {
  pathologies = [basePathology(), { ...basePathology(), id: 2, name: 'Otra patología' }]
  await render(physician)
  await change(control('Buscar patología'), 'OTRA')
  const list = container.querySelector('[aria-label="Patologías"]')
  assert.equal(list.querySelectorAll('.catalog-pathology-list button').length, 1)
  assert.equal(list.querySelector('.catalog-pathology-list button').getAttribute('aria-label'), 'Otra patología')
  await change(control('Buscar patología'), 'sin coincidencias')
  assert.match(list.textContent, /No se encontraron patologías/)
  await change(control('Buscar patología'), '')
  assert.equal(list.querySelectorAll('.catalog-pathology-list button').length, 2)
})

test('cerrar sesión desde el encabezado retira el catálogo y vuelve al login', async () => {
  pathologies = [basePathology()]
  await render(physician)
  assert.match(container.querySelector('[aria-label="Área clínica"]').textContent, /Médico tratante/)
  await click(button('Cerrar sesión'))
  assert.match(container.textContent, /Iniciar sesión/)
  assert.equal(container.querySelector('[aria-label="Área clínica"]'), null)
})

test('cambiar síntomas descarta un resultado de validación anterior', async () => {
  pathologies = [basePathology()]
  await render(physician); await selectPathology()
  await change(control('Seleccionar síntomas presentes'), '1')
  await click(button('Validar sospecha'))
  assert.match(container.textContent, /Sospecha consistente/)
  await change(control('Seleccionar síntomas presentes'), '2')
  assert.doesNotMatch(container.textContent, /Sospecha consistente/)
  assert.equal(container.querySelector('.validation-result'), null)
})
