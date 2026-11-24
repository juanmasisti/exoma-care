// Panel del administrativo: generar y ver las órdenes del día (T04).
import assert from 'node:assert/strict'
import { test } from 'node:test'
import { buenosAiresRoute, button, calls, click, container, crumb, fake, patient, render, summary, text, type } from './transportista-setup.mjs'

const PATH = '/administrativo/ordenes-del-dia'
const cordoba = { ...summary(buenosAiresRoute()), id: 8, province_id: 2, province: 'Córdoba', stops: 1 }

test('muestra las órdenes de hoy con su provincia y avance', async () => {
  fake.routes['2026-11-02'] = [{ ...summary(buenosAiresRoute()), picked_up: 1 }]
  await render(PATH)
  assert.equal(container.querySelector('h1').textContent, 'Órdenes del día')
  assert.equal(crumb(), 'Exoma CareÓrdenes del día')
  assert.equal(container.querySelector('#transporte-date').value, '2026-11-02')
  assert.match(text(), /Buenos Aires.*Pendiente.*Centros retirados: 1 de 3/)
})

test('sin órdenes avisa y genera las que faltan', async () => {
  fake.pending = [summary(buenosAiresRoute()), cordoba]
  await render(PATH)
  assert.match(text(), /No hay órdenes para el lunes, 2 de noviembre de 2026/)
  await click(button('Generar órdenes'))
  assert.deepEqual(calls.at(-1).data, { date: '2026-11-02' })
  assert.equal(container.querySelector('[role="status"]').textContent, 'Se generaron las órdenes que faltaban.')
  assert.deepEqual([...container.querySelectorAll('.turnos-list h2')].map((h) => h.textContent), ['Buenos Aires', 'Córdoba'])
})

test('generar de nuevo no duplica y lo dice', async () => {
  fake.routes['2026-11-02'] = [summary(buenosAiresRoute())]
  await render(PATH)
  await click(button('Generar órdenes'))
  assert.equal(container.querySelector('[role="status"]').textContent, 'Las órdenes de este día ya estaban generadas.')
  assert.equal(container.querySelectorAll('.turnos-list li').length, 1)
})

test('sin muestras listas no genera nada y lo explica', async () => {
  await render(PATH)
  await click(button('Generar órdenes'))
  assert.match(container.querySelector('[role="status"]').textContent, /No hay muestras listas para retirar/)
})

test('fin de semana o API de recorridos caída: muestra el motivo del back', async () => {
  await render(PATH)
  await type(container.querySelector('#transporte-date'), '2026-11-07')
  assert.equal(calls.at(-1).params.date, '2026-11-07')
  fake.generateError = [422, 'El 07/11/2026 es fin de semana: no hay orden del día.']
  await click(button('Generar órdenes'))
  assert.equal(container.querySelector('[role="alert"]').textContent, 'El 07/11/2026 es fin de semana: no hay orden del día.')
  fake.generateError = [502, 'El módulo de recorridos tardó demasiado en responder.']
  await click(button('Generar órdenes'))
  assert.equal(container.querySelector('[role="alert"]').textContent, 'El módulo de recorridos tardó demasiado en responder.')
})

test('error al cargar permite reintentar', async () => {
  fake.networkDown = true
  await render(PATH)
  assert.match(container.querySelector('[role="alert"]').textContent, /Revisá la conexión/)
  fake.networkDown = false
  await click(button('Reintentar'))
  assert.match(text(), /No hay órdenes para/)
})

test('el paciente no entra al panel', async () => {
  await render(PATH, patient)
  assert.notEqual(container.querySelector('h1')?.textContent, 'Órdenes del día')
  assert.ok(!calls.some((call) => call.url === '/transport/daily-routes'))
})
