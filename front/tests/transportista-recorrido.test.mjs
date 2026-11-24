// App del transportista (T04): inicio, orden, retiro por centro y llegada al Laboratorio Central.
import assert from 'node:assert/strict'
import { test } from 'node:test'
import { button, calls, choose, click, container, crumb, fake, go, patient, render, text } from './transportista-setup.mjs'

const link = (label) => {
  const item = [...container.querySelectorAll('main a')].find((a) => a.textContent.trim() === label)
  assert.ok(item, `No se encontró el link ${label}`); return item
}
const status = () => container.querySelector('main [role="status"]')?.textContent
const alert = () => container.querySelector('main [role="alert"]')?.textContent

async function start(provinceId = '1') {
  await render('/transporte')
  await choose(container.querySelector('#transporte-province'), provinceId)
}
async function pickUpCenter(stopId) {
  await go(`/transporte/centro/${stopId}`)
  await click(button('Registrar retiro'))
  await click(button('Confirmar retiro'))
}

test('P1: elige la provincia y ve el resumen y el siguiente centro', async () => {
  await start()
  assert.equal(crumb(), 'Exoma CareRecorrido del día')
  assert.deepEqual(calls.at(-1).params, { date: '2026-11-02', province_id: '1' })
  assert.deepEqual([...container.querySelectorAll('.transporte-kpis li')].map((li) => li.textContent),
    ['3Centros pendientes', '0Centros retirados', '0Muestras a bordo'])
  assert.match(text(), /Siguiente centro.*Parada 1 de 3.*Centro DEMO 3/)
})

test('P1: sin orden para la provincia lo dice', async () => {
  await start('2')
  assert.match(text(), /No hay orden del día para tu provincia hoy/)
})

test('P2: la orden muestra la secuencia fija y solo deja abrir el siguiente', async () => {
  await start()
  await click(link('Ver orden completa'))
  assert.deepEqual([...container.querySelectorAll('.turnos-list h2')].map((h) => h.textContent),
    ['1. Centro DEMO 3', '2. Centro DEMO 2', '3. Centro DEMO 1'])
  assert.deepEqual([...container.querySelectorAll('.turnos-list .turnos-badge')].map((b) => b.textContent), ['Siguiente', 'Pendiente', 'Pendiente'])
  assert.equal([...container.querySelectorAll('.turnos-list a')].length, 1)
})

test('P3 a P5: confirma el retiro, muestra el comprobante y sigue al próximo centro', async () => {
  await start()
  await click(link('Ir al centro'))
  assert.match(text(), /Parada 1 de 3.*Muestras para retirar.*EST-000004/)
  await click(button('Registrar retiro'))
  assert.match(container.querySelector('[aria-label="Confirmar retiro"]').textContent, /¿Confirmás el retiro de 1 muestra de este centro/)
  await click(button('Confirmar retiro'))
  assert.equal(status(), 'Retiro registrado a las 10:15 h: retiraste 1 muestra de este centro.')
  assert.equal(calls.filter((call) => call.url.endsWith('/stops/71/pickup')).length, 1)
  await click(link('Siguiente centro'))
  assert.match(text(), /Centro DEMO 2.*Parada 2 de 3.*Muestras para retirar/)
  assert.equal(status(), undefined)  // el comprobante era del centro anterior
  assert.ok(button('Registrar retiro'))
})

test('un centro que no es el siguiente no se puede retirar', async () => {
  await start()
  await go('/transporte/centro/73')
  assert.match(text(), /El orden es fijo: primero retirá la parada 1/)
  assert.ok(![...container.querySelectorAll('button')].some((b) => b.textContent === 'Registrar retiro'))
})

test('si el back rechaza el retiro muestra el motivo', async () => {
  await start()
  await go('/transporte/centro/71')
  fake.route.next_stop_id = 72  // otro pedido cambió la orden mientras tanto
  await click(button('Registrar retiro'))
  await click(button('Confirmar retiro'))
  assert.equal(alert(), 'El recorrido es fijo: primero hay que retirar la parada anterior.')
})

test('P6: con centros pendientes no deja registrar la llegada', async () => {
  await start()
  await click(link('Muestras a bordo'))
  assert.match(text(), /Todavía no retiraste muestras.*Faltan retirar 3 centros/)
  assert.ok(![...container.querySelectorAll('button')].some((b) => b.textContent === 'Registrar llegada'))
})

test('P7 a P9: con todo retirado registra la llegada y muestra lo recibido', async () => {
  await start()
  for (const stopId of [71, 72, 73]) await pickUpCenter(stopId)
  await go('/transporte/a-bordo')
  assert.match(text(), /EST-000004.*EST-000003.*EST-000001.*EST-000002.*Fin de recorrido/)
  await click(button('Registrar llegada'))
  assert.match(container.querySelector('[aria-label="Confirmar llegada"]').textContent, /con 4 muestras/)
  await click(button('Confirmar llegada'))
  assert.equal(container.querySelector('h1').textContent, 'Llegada registrada')
  assert.equal(status(), 'Se recibieron 4 muestras en el Laboratorio Central.')
  await click(link('Volver al inicio'))
  assert.match(text(), /Recorrido terminado.*13:40 h/)
})

test('si la llegada falla muestra el error y deja reintentar', async () => {
  await start()
  for (const stopId of [71, 72, 73]) await pickUpCenter(stopId)
  await go('/transporte/a-bordo')
  fake.arrivalError = 'No se pudo registrar la llegada.'
  await click(button('Registrar llegada'))
  await click(button('Confirmar llegada'))
  assert.equal(alert(), 'No se pudo registrar la llegada.')
  assert.ok(button('Confirmar llegada'))
})

test('el comprobante del último centro lleva a la llegada y un centro ya retirado no se retira de nuevo', async () => {
  await start()
  await pickUpCenter(71)
  await pickUpCenter(72)
  await pickUpCenter(73)
  assert.ok(link('Registrar llegada'))
  await go('/transporte/centro/71')
  assert.match(text(), /Retirado 10:15 h.*Muestras retiradas.*EST-000004/)
  assert.ok(![...container.querySelectorAll('button')].some((b) => b.textContent === 'Registrar retiro'))
})

test('con la llegada ya registrada, a bordo lo dice y no ofrece registrarla', async () => {
  Object.assign(fake.route, { status: 'arrived', arrived_at: '2026-11-02T13:40:00-03:00', next_stop_id: null })
  fake.route.stops.forEach((stop) => { stop.picked_up_at = '2026-11-02T10:15:00-03:00' })
  await start()
  await go('/transporte/a-bordo')
  assert.match(text(), /La llegada ya fue registrada a las 13:40 h/)
  assert.ok(![...container.querySelectorAll('button')].some((b) => b.textContent === 'Registrar llegada'))
})

test('si falla la recarga después de un retiro, avisa en la pantalla del centro', async () => {
  await start()
  await go('/transporte/centro/71')
  fake.myRouteDown = true
  await click(button('Registrar retiro'))
  await click(button('Confirmar retiro'))
  assert.match(status(), /Retiro registrado/)
  assert.equal(alert(), 'No se pudo cargar la orden del día.Reintentar')
  fake.myRouteDown = false
  await click(button('Reintentar'))
  assert.equal(alert(), undefined)
})

test('error al cargar la orden permite reintentar', async () => {
  await render('/transporte')
  fake.networkDown = true
  await choose(container.querySelector('#transporte-province'), '1')
  assert.match(alert(), /Revisá la conexión/)
  fake.networkDown = false
  await click(button('Reintentar'))
  assert.match(text(), /Siguiente centro/)
})

test('sin provincia elegida las pantallas internas vuelven al inicio', async () => {
  await render('/transporte/a-bordo')
  assert.equal(container.querySelector('h1').textContent, 'Tu recorrido de hoy')
})

test('el paciente no entra al recorrido', async () => {
  await render('/transporte', patient)
  assert.notEqual(container.querySelector('h1')?.textContent, 'Tu recorrido de hoy')
  assert.ok(!calls.some((call) => call.url.startsWith('/transport/')))
})
