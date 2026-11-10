import assert from 'node:assert/strict'
import { after, afterEach, before, beforeEach, test } from 'node:test'
import { Window } from 'happy-dom'
import { createServer } from 'vite'
import React, { act } from 'react'

let server, Component, createRoot, root, dom, container, applied, pending, summary
let instances, throwStart
class Recognition {
  constructor() { instances.push(this); this.aborted = false }
  start() { if (throwStart) throw new Error('provider failed') }
  stop() { this.stopped = true }
  abort() { this.aborted = true }
}
before(async () => {
  const bootstrap = new Window(); globalThis.window = bootstrap; globalThis.document = bootstrap.document
  createRoot = (await import('react-dom/client')).createRoot; bootstrap.close()
  server = await createServer({ server: { middlewareMode: true, hmr: false, ws: false }, appType: 'custom', optimizeDeps: { noDiscovery: true, include: [] } })
  Component = (await server.ssrLoadModule('/src/features/pacientes/ClinicalDictation.jsx')).default
})
after(async () => { await server?.close() })
beforeEach(() => {
  dom = new Window({ url: 'http://localhost:5173/' }); globalThis.window = dom; globalThis.document = dom.document
  globalThis.HTMLElement = dom.HTMLElement; globalThis.IS_REACT_ACT_ENVIRONMENT = true
  dom.SpeechRecognition = Recognition; instances = []; applied = []; pending = []; throwStart = false; summary = 'Texto previo'
  container = document.createElement('div'); document.body.append(container); root = createRoot(container)
})
afterEach(async () => { await act(async () => root.unmount()); dom.happyDOM.abort(); dom.close() })
async function render(extra = {}) {
  await act(async () => root.render(React.createElement(Component, { summary, onApply: value => applied.push(value), onPendingChange: value => pending.push(value), ...extra })))
}
function button(text) { const b = [...container.querySelectorAll('button')].find(b => b.textContent.trim() === text); assert.ok(b, text); return b }
async function click(text) { await act(async () => button(text).click()) }
async function start() { await click('Iniciar dictado'); const r = instances.at(-1); await act(async () => r.onstart()); return r }
async function results(r, parts) { await act(async () => r.onresult({ results: parts.map(([text, final]) => Object.assign([{ transcript: text }], { isFinal: final })) })) }
const draft = () => container.querySelector('textarea')

test('sin soporte conserva escritura manual y no intenta capturar', async () => {
  delete dom.SpeechRecognition; await render()
  assert.match(container.textContent, /escribir manualmente/i); assert.equal(button('Iniciar dictado').disabled, true); assert.equal(instances.length, 0)
})
test('admite prefijo webkit sin iniciar automáticamente', async () => {
  delete dom.SpeechRecognition; dom.webkitSpeechRecognition = Recognition; await render()
  assert.equal(instances.length, 0); const r = await start(); assert.equal(r.lang, 'es-AR'); assert.equal(r.continuous, true)
})
test('finales acumulativos no se duplican y provisionales no pasan al resumen', async () => {
  await render(); const r = await start()
  await results(r, [['Primera frase.', true], ['provisional', false]])
  await results(r, [['Primera frase.', true], ['Segunda frase.', true]])
  assert.equal(applied.length, 0); assert.equal(button('Añadir al resumen').disabled, true)
  await act(async () => r.onend())
  assert.equal(draft().value, 'Primera frase. Segunda frase.')
  await click('Añadir al resumen'); assert.deepEqual(applied, ['Texto previo\n\nPrimera frase. Segunda frase.']); assert.equal(pending.at(-1), false)
})
test('permite revisar borrador y usa el resumen manual más reciente', async () => {
  await render(); const r = await start(); await results(r, [['Texto reconocido', true]]); await act(async () => r.onend())
  await act(async () => { Object.getOwnPropertyDescriptor(dom.HTMLTextAreaElement.prototype, 'value').set.call(draft(), 'Texto corregido'); draft().dispatchEvent(new dom.Event('input', { bubbles: true })) })
  summary = 'Edición manual nueva'; await render(); await click('Añadir al resumen')
  assert.equal(applied[0], 'Edición manual nueva\n\nTexto corregido')
})
test('detener espera el resultado final antes de habilitar revisión', async () => {
  await render(); const r = await start(); await click('Detener dictado'); assert.equal(r.stopped, true)
  await results(r, [['Final al detener', true]]); assert.equal(button('Añadir al resumen').disabled, true)
  await act(async () => r.onend()); assert.equal(button('Añadir al resumen').disabled, false)
})
test('descartar aborta e ignora resultados tardíos', async () => {
  await render(); const r = await start(); const late = r.onresult; await results(r, [['No guardar', true]])
  await click('Descartar dictado'); assert.equal(r.aborted, true)
  await act(async () => late({ results: [Object.assign([{ transcript: 'Tardío' }], { isFinal: true })] }))
  assert.equal(applied.length, 0); assert.equal(pending.at(-1), false); assert.equal(draft(), null)
})
test('desmontar cancela captura y no aplica texto', async () => {
  await render(); const r = await start(); await act(async () => root.render(null)); assert.equal(r.aborted, true); assert.equal(applied.length, 0)
})
test('permiso denegado libera controles y explica cómo continuar', async () => {
  await render(); await click('Iniciar dictado'); const r = instances[0]
  await act(async () => r.onerror({ error: 'not-allowed' }))
  assert.match(container.querySelector('[role="alert"]').textContent, /permiso/i)
  assert.equal(button('Iniciar dictado').disabled, false); assert.equal(pending.at(-1), false)
})
test('fallo al iniciar no bloquea la escritura ni inventa texto', async () => {
  throwStart = true; await render(); await click('Iniciar dictado')
  assert.ok(container.querySelector('[role="alert"]')); assert.equal(pending.at(-1), false); assert.equal(applied.length, 0)
})
test('error de red conserva solo finales para revisión', async () => {
  await render(); const r = await start(); await results(r, [['Confirmado', true], ['Incompleto', false]])
  await act(async () => r.onerror({ error: 'network' }))
  assert.equal(draft().value, 'Confirmado'); assert.match(container.textContent, /conexión/i); assert.equal(applied.length, 0)
  assert.match(container.querySelector('[role="alert"]').textContent, /Conservamos/)
})

test('error de red inmediato orienta al usuario sin afirmar que hay texto conservado', async () => {
  await render(); await click('Iniciar dictado'); const r = instances[0]
  await act(async () => { r.onerror({ error: 'network' }); r.onend() })
  const message = container.querySelector('[role="alert"]').textContent
  assert.match(message, /Chrome/); assert.doesNotMatch(message, /Conservamos/)
  assert.equal(pending.at(-1), false); assert.equal(applied.length, 0)
  assert.equal(button('Iniciar dictado').disabled, false)
  assert.equal(Boolean(draft()), false)
  const retry = await start(); await results(retry, [['Nuevo intento', true]])
  await act(async () => retry.onend()); await click('Añadir al resumen')
  assert.equal(applied[0], 'Texto previo\n\nNuevo intento')
})
test('no trunca ni permite añadir más de 20000 caracteres', async () => {
  summary = 'a'.repeat(19999); await render(); const r = await start(); await results(r, [['Texto', true]]); await act(async () => r.onend())
  assert.equal(button('Añadir al resumen').disabled, true); assert.match(container.textContent, /20.000|20000/); assert.equal(draft().value, 'Texto')
})
test('una sesión con solo intermedios no produce borrador aceptable', async () => {
  await render(); const r = await start(); await results(r, [['No final', false]]); await act(async () => r.onend())
  assert.equal(applied.length, 0); assert.equal(pending.at(-1), false); assert.match(container.textContent, /no se reconoció/i)
})

test('contexto inseguro deshabilita captura', async () => {
  Object.defineProperty(dom, 'isSecureContext', { value: false }); await render()
  assert.equal(button('Iniciar dictado').disabled, true); assert.match(container.textContent, /HTTPS o localhost/)
})
test('timeout al detener libera controles y conserva finales', async t => {
  await render(); const r = await start(); await results(r, [['Frase final', true]])
  t.mock.timers.enable({ apis: ['setTimeout'] })
  try {
    await click('Detener dictado'); await act(async () => t.mock.timers.tick(4001))
    assert.equal(r.aborted, true); assert.equal(button('Añadir al resumen').disabled, false)
    assert.equal(draft().value, 'Frase final'); assert.ok(container.querySelector('[role="alert"]'))
  } finally { t.mock.timers.reset() }
})
test('timeout esperando inicio libera captura sin texto ficticio', async t => {
  await render(); t.mock.timers.enable({ apis: ['setTimeout'] })
  try {
    await click('Iniciar dictado'); await act(async () => t.mock.timers.tick(12001))
    assert.equal(instances[0].aborted, true); assert.equal(pending.at(-1), false); assert.equal(applied.length, 0)
  } finally { t.mock.timers.reset() }
})

test('un inicio tardío después de detener no cancela el timeout de finalización', async t => {
  await render(); t.mock.timers.enable({ apis: ['setTimeout'] })
  try {
    await click('Iniciar dictado'); const r = instances[0]; await click('Detener dictado')
    await act(async () => r.onstart())
    await act(async () => t.mock.timers.tick(4001))
    assert.equal(r.aborted, true); assert.equal(pending.at(-1), false)
  } finally { t.mock.timers.reset() }
})

test('vaciar el borrador conserva el editor para reescribir la corrección', async () => {
  await render(); const r = await start(); await results(r, [['Texto para corregir', true]]); await act(async () => r.onend())
  async function edit(value) {
    assert.ok(draft(), 'Debe conservarse el editor aunque quede vacío')
    await act(async () => { Object.getOwnPropertyDescriptor(dom.HTMLTextAreaElement.prototype, 'value').set.call(draft(), value); draft().dispatchEvent(new dom.Event('input', { bubbles: true })) })
  }
  await edit(''); assert.ok(draft()); assert.equal(button('Añadir al resumen').disabled, true)
  await edit('Corrección completa'); await click('Añadir al resumen')
  assert.equal(applied[0], 'Texto previo\n\nCorrección completa')
})

test('callbacks de una sesión descartada no contaminan una nueva', async () => {
  await render(); const old = await start(); const stale = { result: old.onresult, error: old.onerror, end: old.onend }
  await click('Descartar dictado'); const current = await start()
  await results(current, [['Sesión actual', true]])
  await act(async () => {
    stale.result({ results: [Object.assign([{ transcript: 'Sesión anterior' }], { isFinal: true })] })
    stale.error({ error: 'network' }); stale.end()
  })
  assert.equal(button('Añadir al resumen').disabled, true); assert.equal(container.querySelector('[role="alert"]'), null)
  await act(async () => current.onend()); await click('Añadir al resumen')
  assert.equal(applied[0], 'Texto previo\n\nSesión actual')
})
