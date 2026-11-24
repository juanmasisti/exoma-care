// Envío del lote (T06) dentro del detalle del lote, como lo ve el administrativo.
import assert from 'node:assert/strict'
import { test } from 'node:test'
import { act } from 'react'
import { PICKUP_AT, button, calls, click, container, dom, fake, hasButton, render, renderAlone, section, shipment, type } from './envio-setup.mjs'

const posts = () => calls.filter((c) => c.method === 'post').map((c) => [c.url, c.data])

test('un lote cerrado y autorizado muestra el estado, las descargas y el formulario del retiro', async () => {
  await render()
  assert.equal(calls[0].authorization, 'Bearer test-token')
  const text = section().textContent
  assert.match(text, /Estado.*Cerrado/)
  assert.match(text, /Autorización del Ministerio de Salud.*Autorizado.*SIMULADO/)
  assert.ok(hasButton('Descargar CSV') && hasButton('Descargar autorización'))
  assert.ok(section().querySelector('#envio-retiro'))
  assert.equal(hasButton('Pedir autorización'), false)
  assert.equal(hasButton('Actualizar estado'), false)
  assert.doesNotMatch(container.textContent, /Corea/i)
})

test('sin autorización se puede pedir otra vez', async () => {
  fake.shipment = shipment('closed', { has_csv: false, has_authorization: false })
  await render()
  assert.match(section().textContent, /Pendiente/)
  assert.equal(section().querySelector('#envio-retiro'), null)
  await click('Pedir autorización')
  assert.deepEqual(posts(), [['/shipments/1/authorization', undefined]])
  assert.match(section().textContent, /Autorizado/)
  assert.ok(section().querySelector('#envio-retiro'))
})

test('si el Ministerio no responde se muestra el error del back', async () => {
  fake.shipment = shipment('closed', { has_csv: false, has_authorization: false })
  fake.reject = { url: '/shipments/1/authorization', status: 502, detail: 'El Ministerio de Salud no respondió. Reintentá la autorización.' }
  await render()
  await click('Pedir autorización')
  assert.equal(section().querySelector('[role="alert"]').textContent, 'El Ministerio de Salud no respondió. Reintentá la autorización.')
  assert.equal(button('Pedir autorización').disabled, false)
})

test('programar el retiro manda la hora argentina y pasa a esperar a FedEx', async () => {
  await render()
  assert.equal(button('Programar retiro').disabled, true)
  await type(section().querySelector('#envio-retiro'), '2026-12-02T10:00')
  await act(async () => section().querySelector('form').dispatchEvent(new dom.Event('submit', { bubbles: true, cancelable: true })))
  await new Promise((resolve) => setTimeout(resolve, 50))
  assert.deepEqual(posts(), [['/shipments/1/pickup', { scheduled_at: PICKUP_AT }]])
  const text = section().textContent
  assert.match(text, /Esperando el retiro de FedEx/)
  assert.match(text, /Retiro de FedEx.*miércoles, 2 de diciembre de 2026, 10:00 h/)
  assert.equal(section().querySelector('#envio-retiro'), null)
  assert.ok(hasButton('Actualizar estado'))
})

test('un retiro fuera de horario muestra el motivo y deja el formulario', async () => {
  fake.reject = { url: '/shipments/1/pickup', status: 422, detail: 'FedEx retira en días hábiles, de 9 a 18 h.' }
  await render()
  await type(section().querySelector('#envio-retiro'), '2026-12-02T19:00')
  await act(async () => section().querySelector('form').dispatchEvent(new dom.Event('submit', { bubbles: true, cancelable: true })))
  await new Promise((resolve) => setTimeout(resolve, 50))
  assert.equal(section().querySelector('[role="alert"]').textContent, 'FedEx retira en días hábiles, de 9 a 18 h.')
  assert.ok(section().querySelector('#envio-retiro'))
})

test('actualizar el estado pasa el lote al viaje cuando FedEx ya retiró', async () => {
  fake.shipment = shipment('awaiting_pickup', { pickup_at: PICKUP_AT, courier_pickup_id: 'uuid-demo' })
  fake.afterRefresh = 'in_transit_to_sequencing_lab'
  await render()
  await click('Actualizar estado')
  assert.deepEqual(posts(), [['/shipments/1/refresh', undefined]])
  assert.match(section().textContent, /En viaje al laboratorio de secuenciación/)
  assert.equal(hasButton('Actualizar estado'), false)
})

test('si FedEx no responde al actualizar, se avisa y el lote sigue esperando', async () => {
  fake.shipment = shipment('awaiting_pickup', { pickup_at: PICKUP_AT, courier_pickup_id: 'uuid-demo' })
  fake.reject = { url: '/shipments/1/refresh', status: 502, detail: 'FedEx tardó demasiado en responder.' }
  await render()
  await click('Actualizar estado')
  assert.equal(section().querySelector('[role="alert"]').textContent, 'FedEx tardó demasiado en responder.')
  assert.match(section().textContent, /Esperando el retiro de FedEx/)
})

test('las descargas van por la API con el token y muestran el error del back', async (t) => {
  const clicked = []
  t.mock.method(URL, 'createObjectURL', () => 'blob:demo')
  t.mock.method(URL, 'revokeObjectURL', () => {})
  t.mock.method(dom.HTMLAnchorElement.prototype, 'click', function () { clicked.push(this.download) })
  await render()
  await click('Descargar CSV')
  await click('Descargar autorización')
  const downloads = calls.filter((c) => c.responseType === 'blob').map((c) => [c.url, c.authorization])
  assert.deepEqual(downloads, [['/shipments/1/csv', 'Bearer test-token'], ['/shipments/1/authorization.pdf', 'Bearer test-token']])
  assert.deepEqual(clicked, ['lote-1.csv', 'lote-1-autorizacion.pdf'])

  fake.reject = { url: '/shipments/1/csv', status: 404, detail: 'El lote todavía no tiene ese archivo.' }
  await click('Descargar CSV')
  assert.equal(section().querySelector('[role="alert"]').textContent, 'El lote todavía no tiene ese archivo.')
})

test('un lote armándose todavía no tiene envío', async () => {
  fake.shipment = shipment('assembling', { has_csv: false, has_authorization: false })
  await render()
  assert.match(section().textContent, /El envío se prepara cuando se cierra el lote/)
  assert.equal(section().querySelectorAll('button').length, 0)
})

test('un error al cargar el envío se puede reintentar', async () => {
  fake.loadDown = true
  await render()
  assert.ok(section().querySelector('[role="alert"]'))
  fake.loadDown = false
  await click('Reintentar')
  assert.equal(section().querySelector('[role="alert"]'), null)
  assert.match(section().textContent, /Cerrado/)
})

test('le avisa al detalle del lote solo cuando el envío cambia el lote', async (t) => {
  const onChange = t.mock.fn()
  fake.shipment = shipment('closed', { has_csv: false, has_authorization: false })
  fake.reject = { url: '/shipments/1/authorization', status: 502, detail: 'El Ministerio de Salud no respondió. Reintentá la autorización.' }
  await renderAlone(onChange)
  await click('Pedir autorización')
  assert.equal(onChange.mock.callCount(), 0)  // falló: el lote no cambió
  fake.reject = null
  await click('Pedir autorización')
  assert.equal(onChange.mock.callCount(), 1)
  t.mock.method(URL, 'createObjectURL', () => 'blob:demo')
  t.mock.method(URL, 'revokeObjectURL', () => {})
  t.mock.method(dom.HTMLAnchorElement.prototype, 'click', () => {})
  await click('Descargar CSV')
  assert.equal(onChange.mock.callCount(), 1)  // descargar no cambia el lote
})
