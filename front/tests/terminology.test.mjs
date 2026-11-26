import assert from 'node:assert/strict'
import { after, before, test } from 'node:test'
import { Window } from 'happy-dom'
import { createServer } from 'vite'
import React, { act } from 'react'
let server, Picker, api, createRoot
before(async () => {
  globalThis.window = new Window(); globalThis.document = window.document
  globalThis.IS_REACT_ACT_ENVIRONMENT = true
  createRoot = (await import('react-dom/client')).createRoot
  server = await createServer({ server: { middlewareMode: true, hmr: false }, appType: 'custom' })
  Picker = (await server.ssrLoadModule('/src/features/patologias/SymptomPicker.jsx')).default
  api = (await server.ssrLoadModule('/src/services/api.js')).api
})
after(async () => { await server?.close(); window.close() })
test('SNOMED requires explicit selection and imports canonical local identity', async () => {
  const calls = []; let chosen
  api.defaults.adapter = async config => {
    calls.push(config.url)
    const data = config.url === '/symptoms' ? [] : config.url.endsWith('/import')
      ? { id: 42, code: '386661006', label: 'fiebre', code_system: 'SNOMED' }
      : [{ code: '386661006', label: 'fiebre', code_system: 'SNOMED', selection_token: 'signed' }]
    return { data, status: 200, headers: {}, config }
  }
  const container = document.createElement('div'); document.body.append(container)
  const root = createRoot(container)
  try {
    await act(async () => root.render(React.createElement(Picker, { label: 'Síntomas', selected: [], onChange: value => { chosen = value } })))
    assert.equal(container.querySelector('[aria-label="Fuente de síntomas"]'), null)
    assert.equal(calls.includes('/terminology/symptoms'), false)
    const input = container.querySelector('input')
    await act(async () => {
      Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set.call(input, 'fiebre')
      input.dispatchEvent(new window.Event('input', { bubbles: true }))
    })
    await act(async () => { await new Promise(resolve => setTimeout(resolve, 300)) })
    assert.equal(chosen, undefined)
    const select = container.querySelector('select:not([aria-label])')
    await act(async () => { select.value = '386661006'; select.dispatchEvent(new window.Event('change', { bubbles: true })) })
    assert.equal(calls.includes('/symptoms'), false)
    assert.equal(chosen[0].id, 42)
    assert.equal(chosen[0].code_system, 'SNOMED')
  } finally { await act(async () => root.unmount()); container.remove() }
})
