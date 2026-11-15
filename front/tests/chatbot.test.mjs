import assert from 'node:assert/strict'
import { after, afterEach, before, beforeEach, test } from 'node:test'
import { Window } from 'happy-dom'
import { createServer } from 'vite'
import React, { act } from 'react'
import { AxiosError } from 'axios'

let server, Harness, api, setSession, createRoot, root, dom, container, calls, available, fail, delayed, resolveReply
const patient = { access_token: 'test', role: 'patient' }
before(async () => {
  const boot = new Window(); globalThis.window = boot; globalThis.document = boot.document
  createRoot = (await import('react-dom/client')).createRoot; boot.close()
  server = await createServer({ server: { middlewareMode: true, hmr: false, ws: false }, appType: 'custom', optimizeDeps: { noDiscovery: true, include: [] } })
  Harness = (await server.ssrLoadModule('/tests/harness.jsx')).default
  api = (await server.ssrLoadModule('/src/services/api.js')).api
  setSession = (await server.ssrLoadModule('/src/services/session.js')).setSession
})
after(async () => server?.close())
beforeEach(() => {
  dom = new Window({ url: 'http://localhost:5173/' }); globalThis.window = dom; globalThis.document = dom.document
  globalThis.HTMLElement = dom.HTMLElement; globalThis.IS_REACT_ACT_ENVIRONMENT = true
  container = document.createElement('div'); document.body.append(container); root = createRoot(container)
  calls = []; available = false; fail = false; delayed = false
  api.defaults.adapter = async config => {
    calls.push(config)
    let data
    if (config.url === '/chatbot/status') data = { available }
    else if (config.url === '/chatbot/messages') {
      if (fail) throw new AxiosError('failure', 'ERR_BAD_RESPONSE', config, null, { status: 503, data: { detail: { message: 'Servicio no disponible' } } })
      if (delayed) await new Promise(resolve => { resolveReply = resolve })
      data = { answer: '<img src=x onerror=alert(1)> Respuesta de prueba', conversation_token: 'signed-handle', kind: 'respuesta' }
    } else if (config.url === '/patients') data = { items: [], total: 0 }
    else if (config.url === '/pathologies') data = []
    else throw new Error('Unexpected request ' + config.url)
    return { data, status: 200, headers: {}, config }
  }
})
afterEach(async () => { await act(async () => { root.unmount(); setSession(null) }); dom.happyDOM.abort(); dom.close() })
async function render(session = patient) { await act(async () => { setSession(session); root.render(React.createElement(Harness, { initialEntries: ['/paciente/consultas'] })) }) }
const button = text => [...container.querySelectorAll('button')].find(b => b.textContent.trim() === text)
async function click(text) { assert.ok(button(text), text); await act(async () => button(text).click()) }
async function type(value) {
  await act(async () => {
    const area = container.querySelector('textarea'); assert.ok(area)
    Object.getOwnPropertyDescriptor(dom.HTMLTextAreaElement.prototype, 'value').set.call(area, value)
    area.dispatchEvent(new dom.Event('input', { bubbles: true }))
  })
}

test('sin configurar muestra indisponibilidad y no envía preguntas', async () => {
  await render(); assert.match(container.textContent, /aún no está disponible/)
  assert.equal(button('Enviar pregunta').disabled, true)
  assert.equal(calls.filter(c => c.method === 'post').length, 0)
  assert.ok(container.querySelector('a[href="/paciente/turnos/reservar"]'))
})
test('verificar disponibilidad habilita envío sin recargar', async () => {
  await render(); available = true; await click('Verificar disponibilidad'); await type('¿Qué es Fabry?')
  await click('Enviar pregunta')
  assert.deepEqual(JSON.parse(calls.find(c => c.method === 'post').data), { question: '¿Qué es Fabry?', conversation_token: null })
  assert.match(container.textContent, /Respuesta de prueba/)
  assert.equal(Boolean(container.querySelector('img')), false)
  assert.equal(container.querySelector('textarea').value, '')
  await click('Ver última respuesta')
  assert.equal(document.activeElement, container.querySelector('.chat-messages').lastElementChild)
})
test('fallo conserva pregunta y permite reintentar sin duplicar mensajes', async () => {
  available = true; fail = true; await render(); await type('Pregunta pendiente'); await click('Enviar pregunta')
  assert.equal(container.querySelector('textarea').value, 'Pregunta pendiente')
  assert.ok(container.querySelector('[role="alert"]'))
  fail = false; await click('Enviar pregunta')
  assert.equal(container.querySelectorAll('.chat-message').length, 2)
})
test('envío pendiente impide duplicados y salir cancela la solicitud', async () => {
  available = true; delayed = true; await render(); await type('Pregunta'); await click('Enviar pregunta')
  assert.equal(button('Enviando…').disabled, true)
  assert.equal(container.querySelector('.chat-question p').textContent, 'Pregunta')
  assert.match(container.querySelector('.chat-messages').textContent, /Preparando respuesta/)
  assert.equal(Boolean(container.querySelector('.chat-empty')), false)
  const request = calls.find(c => c.method === 'post')
  await act(async () => root.render(null))
  assert.equal(request.signal.aborted, true)
  await act(async () => resolveReply())
  assert.equal(container.textContent, '')
})
test('sin sesión redirige a login sin consultar proveedor', async () => {
  await render(null); assert.equal(calls.length, 0); assert.ok(document.getElementById('identifier'))
})
test('médico no accede a consultas ni ve enlace', async () => {
  await render({ access_token: 'test', role: 'treating_physician' })
  assert.equal(calls.some(c => c.url.startsWith('/chatbot')), false)
  assert.equal(Boolean(container.querySelector('a[href="/paciente/consultas"]')), false)
})

test('fallo al consultar disponibilidad permite recuperarse', async () => {
  const adapter = api.defaults.adapter
  api.defaults.adapter = async () => { throw new Error('offline') }
  await render(); assert.match(container.textContent, /No pudimos comprobar/)
  api.defaults.adapter = adapter; available = true
  await click('Verificar disponibilidad'); await type('  ')
  assert.equal(button('Enviar pregunta').disabled, true)
  await type('Pregunta válida'); assert.equal(button('Enviar pregunta').disabled, false)
})

test('cambio de sesión descarta la conversación anterior', async () => {
  available = true; await render(); await type('Pregunta del primer paciente'); await click('Enviar pregunta')
  assert.equal(container.querySelectorAll('.chat-message').length, 2)
  await act(async () => setSession({ access_token: 'another-user', role: 'patient' }))
  assert.equal(container.querySelectorAll('.chat-message').length, 0)
  assert.equal(container.querySelector('textarea').value, '')
})

test('continuación envía referencia firmada y nueva conversación la limpia', async () => {
  available = true; await render(); await type('Primera pregunta'); await click('Enviar pregunta')
  await type('¿Y cómo se hereda?'); await click('Enviar pregunta')
  assert.equal(JSON.parse(calls.filter(c => c.method === 'post')[1].data).conversation_token, 'signed-handle')
  await click('Nueva conversación'); await type('Otra pregunta'); await click('Enviar pregunta')
  assert.equal(JSON.parse(calls.filter(c => c.method === 'post')[2].data).conversation_token, null)
  assert.equal(container.querySelector('textarea').maxLength, 1000)
})

test('429 espera Retry-After y reintenta una sola vez', async () => {
  const { askChatbot } = await server.ssrLoadModule('/src/features/chatbot/api.js')
  let count = 0; const waits = []
  api.defaults.adapter = async config => {
    count++
    throw new AxiosError('limit', 'ERR_BAD_RESPONSE', config, null, { status: 429, data: {}, headers: { 'retry-after': '7' } })
  }
  await assert.rejects(() => askChatbot('Hola', null, new AbortController().signal, () => {}, async seconds => waits.push(seconds)))
  assert.equal(count, 2); assert.deepEqual(waits, [7])
})

test('cancelar durante espera evita el segundo envío', async () => {
  const { askChatbot } = await server.ssrLoadModule('/src/features/chatbot/api.js')
  let count = 0; const controller = new AbortController()
  api.defaults.adapter = async config => {
    count++
    throw new AxiosError('limit', 'ERR_BAD_RESPONSE', config, null, { status: 429, data: {}, headers: { 'retry-after': '60' } })
  }
  const promise = askChatbot('Hola', null, controller.signal, () => controller.abort())
  await assert.rejects(promise)
  assert.equal(count, 1)
})
