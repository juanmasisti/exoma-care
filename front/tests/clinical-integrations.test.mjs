import assert from 'node:assert/strict'
import { after, afterEach, before, beforeEach, test } from 'node:test'
import { Window } from 'happy-dom'
import { createServer } from 'vite'
import React, { act } from 'react'

let server, Advice, Panel, api, root, container, dom, createRoot
const symptoms = [{ id: 1, code: '247398009', label: 'Dolor', code_system: 'SNOMED' }]
const response = { result: { compatible: false, estrategia: 'MENOR_DIFERENCIA', patologias: [], ranking: [], mensaje: 'Sin cardinales' }, excluded_symptom_ids: [] }
before(async () => {
  const bootstrap = new Window()
  globalThis.window = bootstrap; globalThis.document = bootstrap.document
  createRoot = (await import('react-dom/client')).createRoot
  bootstrap.close()
  server = await createServer({ server: { middlewareMode: true, hmr: false }, appType: 'custom' })
  Advice = (await server.ssrLoadModule('/src/features/pacientes/CDSSAdvice.jsx')).default
  Panel = (await server.ssrLoadModule('/src/features/patologias/ExternalPathologyPanel.jsx')).default
  api = (await server.ssrLoadModule('/src/services/api.js')).api
})
after(async () => { await server?.close() })
beforeEach(() => {
  dom = new Window({ url: 'http://localhost/' })
  globalThis.window = dom; globalThis.document = dom.document
  globalThis.IS_REACT_ACT_ENVIRONMENT = true
  container = document.createElement('div'); document.body.append(container)
  root = createRoot(container)
})
afterEach(async () => { await act(async () => root.unmount()); dom.close() })
const button = (text) => [...container.querySelectorAll('button')].find((b) => b.textContent.includes(text))
const reply = (config, data) => ({ data, status: 200, statusText: 'OK', headers: {}, config })

test('CDSS sends IDs explicitly and clears results when symptoms change', async () => {
  const requests = []
  api.defaults.adapter = async (config) => { requests.push(JSON.parse(config.data)); return reply(config, response) }
  await act(async () => root.render(React.createElement(Advice, { symptoms })))
  assert.equal(requests.length, 0)
  await act(async () => button('Consultar orientación').click())
  assert.deepEqual(requests, [{ symptom_ids: [1] }])
  assert.match(container.textContent, /CDSS no encontró compatibilidad/)
  await act(async () => root.render(React.createElement(Advice, { symptoms: [...symptoms, { id: 2, code_system: 'DEMO' }] })))
  assert.doesNotMatch(container.textContent, /Sin cardinales/)
})

test('stale CDSS response cannot populate changed selection', async () => {
  let resolve
  api.defaults.adapter = (config) => new Promise((done) => { resolve = () => done(reply(config, response)) })
  await act(async () => root.render(React.createElement(Advice, { symptoms })))
  await act(async () => button('Consultar orientación').click())
  await act(async () => root.render(React.createElement(Advice, { symptoms: [] })))
  await act(async () => resolve())
  assert.doesNotMatch(container.textContent, /Sin cardinales/)
  assert.equal(button('Consultar orientación').disabled, true)
})

test('external identity is displayed separately without overwriting clinical rule', async () => {
  let requests = 0
  api.defaults.adapter = async () => { requests++; throw new Error('unexpected') }
  await act(async () => root.render(React.createElement(Panel, { pathology: { id: 1, name: 'Local', apigen_code: 'FABRY', apigen_group: '', cdss_code: 'FABRY' }, onLinked: () => assert.fail('unexpected'), onCriteriaDraft: () => assert.fail('unexpected') })))
  assert.match(container.textContent, /Identidad asociada: FABRY/)
  assert.equal(button('Asociar identidad'), undefined)
  assert.equal(requests, 0)
})


const remotePathology = { codigo: 'FABRY', nombre: 'Fabry', genes: ['GLA'], herencia: 'ligada_al_x', de_grupo: false }
async function chooseExternalPathology() {
  await act(async () => button('Consultar catálogos').click())
  await act(async () => {
    const select = container.querySelector('[aria-label="Patología Apigen"]')
    select.value = 'false:FABRY'
    select.dispatchEvent(new dom.Event('change', { bubbles: true }))
  })
}

test('late identity response cannot update parent after pathology changes', async () => {
  let resolve, linked = 0
  api.defaults.adapter = (config) => {
    if (config.method === 'put') return new Promise((done) => { resolve = () => done(reply(config, { id: 1, apigen_code: 'FABRY' })) })
    return Promise.resolve(reply(config, config.url.includes('/apigen/') ? [remotePathology] : []))
  }
  await act(async () => root.render(React.createElement(Panel, { key: 1, pathology: { id: 1, name: 'Primera' }, onLinked: () => linked++ })))
  await chooseExternalPathology()
  await act(async () => button('Asociar identidad').click())
  assert.equal(typeof resolve, 'function')
  await act(async () => root.render(React.createElement(Panel, { key: 2, pathology: { id: 2, name: 'Segunda' }, onLinked: () => linked++ })))
  await act(async () => resolve())
  assert.equal(linked, 0)
  assert.match(container.textContent, /Asociar a: Segunda/)
})

test('parent save disables external mutations and draft application', async () => {
  const clinical = [{ codigo: 'FABRY', nombre: 'Fabry', sintomas: [] }]
  api.defaults.adapter = async (config) => reply(config, config.url.endsWith('/draft') ? { codigo: 'FABRY', cardinals: symptoms, secondary: [] } : config.url.includes('/apigen/') ? [remotePathology] : clinical)
  const props = { pathology: { id: 1, name: 'Local' }, onLinked: () => assert.fail('unexpected'), onCriteriaDraft: () => assert.fail('unexpected') }
  await act(async () => root.render(React.createElement(Panel, props)))
  await chooseExternalPathology()
  await act(async () => button('Preparar criterios de').click())
  await act(async () => {
    const select = container.querySelector('[aria-label="Cardinal del borrador"]')
    select.value = '1'; select.dispatchEvent(new dom.Event('change', { bubbles: true }))
  })
  await act(async () => root.render(React.createElement(Panel, { ...props, disabled: true })))
  assert.equal(button('Asociar identidad').disabled, true)
  assert.equal(button('Preparar criterios de').disabled, true)
  assert.equal(button('Usar criterios').disabled, true)
  assert.equal(button('Crear en Apigen').disabled, true)
})
