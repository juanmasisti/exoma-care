// App del transportista (T04): inicio, orden, retiro por centro y llegada al Laboratorio Central.
import assert from 'node:assert/strict'
import { beforeEach, test } from 'node:test'
import { act } from 'react'
import { button, calls, choose, click, container, crumb, dom, fake, go, patient, render, summary, text } from './transportista-setup.mjs'

// Órdenes ya generadas hoy: de acá salen las provincias del selector. Córdoba no tiene detalle (my-route da 404).
beforeEach(() => {
  fake.routes['2026-11-02'] = [summary(fake.route), { ...summary(fake.route), id: 8, province_id: 2, province: 'Córdoba' }]
})

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
    ['3Centros pendientes', '0Centros retirados', '4Muestras para retirar', '0Muestras a bordo'])
  assert.equal(container.querySelector('progress[aria-label="Avance del recorrido"]').value, 0)
  assert.doesNotMatch(text(), /°C/)  // el PO pidió sacar la temperatura (dominio)
  assert.match(text(), /Siguiente centro.*Parada 1 de 3.*Centro DEMO 3/)
})

test('P1: las provincias salen de las órdenes de hoy, no del turnero', async () => {
  await render('/transporte')
  assert.deepEqual([...container.querySelectorAll('#transporte-province option')].map((o) => o.textContent),
    ['Elegí tu provincia', 'Buenos Aires', 'Córdoba'])
  assert.deepEqual(calls[0], { url: '/transport/daily-routes', method: 'get', params: { date: '2026-11-02' }, data: undefined })
  assert.ok(!calls.some((call) => call.url === '/provinces'))
  assert.equal(alert(), undefined)
})

test('P1: sin órdenes generadas hoy lo dice', async () => {
  fake.routes = {}
  await render('/transporte')
  assert.match(text(), /Hoy no hay órdenes del día generadas/)
  assert.equal(container.querySelector('#transporte-province'), null)
})

test('P1: sin orden para la provincia lo dice', async () => {
  await start('2')
  assert.match(text(), /No hay orden del día para tu provincia hoy/)
})

test('P2: la orden muestra la secuencia fija y solo deja abrir el siguiente', async () => {
  await start()
  await click(link('Ver orden completa'))
  assert.deepEqual([...container.querySelectorAll('.transporte-timeline h2')].map((h) => h.textContent),
    ['1. Centro DEMO 3', '2. Centro DEMO 2', '3. Centro DEMO 1'])
  assert.deepEqual([...container.querySelectorAll('.transporte-timeline .turnos-badge')].map((b) => b.textContent), ['Siguiente', 'Pendiente', 'Pendiente'])
  assert.equal([...container.querySelectorAll('.transporte-timeline a')].length, 1)
  assert.match(container.querySelector('.transporte-timeline').textContent, /Calle DEMO 1, La Plata · 2 muestras/)
  const map = container.querySelector('[aria-label="Mapa del recorrido"]')
  assert.deepEqual([...map.querySelectorAll('.transporte-pin')].map((pin) => pin.textContent), ['LC', '1', '2', '3'])
  assert.equal(map.querySelectorAll('path.leaflet-interactive').length, 1)  // la línea del recorrido
})

test('P3: las muestras van en una tabla con código, volumen y hora de extracción (— si no la hay)', async () => {
  fake.route.next_stop_id = 73
  await start()
  await go('/transporte/centro/73')
  const rows = [...container.querySelectorAll('.transporte-table tbody tr')].map((row) => [...row.children].map((cell) => cell.textContent))
  assert.deepEqual(rows, [['EST-000001', '4 ml', '30/10 09:30 h'], ['EST-000002', '4 ml', '—']])
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

test('P4: la confirmación del retiro es una ventana modal que se cancela sin llamar al back', async () => {
  await start()
  await go('/transporte/centro/71')
  button('Registrar retiro').focus()  // como un clic de verdad, que deja el foco en el botón
  await click(button('Registrar retiro'))
  const dialog = container.querySelector('[role="dialog"]')
  assert.equal(dialog.getAttribute('aria-modal'), 'true')
  assert.equal(dialog.getAttribute('aria-label'), 'Confirmar retiro')
  assert.equal(document.activeElement.textContent, 'Confirmar retiro')
  await click(button('Cancelar'))
  assert.equal(container.querySelector('[role="dialog"]'), null)
  assert.equal(document.activeElement.textContent, 'Registrar retiro')  // el foco vuelve al botón que la abrió
  await click(button('Registrar retiro'))
  await escape()
  assert.equal(container.querySelector('[role="dialog"]'), null)
  assert.ok(!calls.some((call) => call.url.endsWith('/pickup')))
})

const escape = () => act(async () => document.dispatchEvent(new dom.KeyboardEvent('keydown', { key: 'Escape', bubbles: true })))

test('P5: el comprobante del retiro tiene sello de hora, centro, cantidad y custodia transferida', async () => {
  await start()
  await pickUpCenter(71)
  const receipt = container.querySelector('[aria-label="Retiro registrado"]')
  assert.deepEqual([...receipt.querySelectorAll('dt')].map((dt) => `${dt.textContent}: ${dt.nextElementSibling.textContent}`),
    ['Hora: 10:15 h', 'Lugar: Centro DEMO 3', 'Muestras: 1', 'Custodia: Transferida al transportista'])
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
  assert.equal(document.activeElement.textContent, 'Confirmar retiro')  // el foco vuelve adentro de la ventana
  await escape()  // con el error a la vista, Escape igual la cierra
  assert.equal(container.querySelector('[role="dialog"]'), null)
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
  assert.match(text(), /Fin del recorrido.*EST-000004.*EST-000003.*EST-000001.*EST-000002.*Balance de la jornada/)
  await click(button('Registrar llegada'))
  assert.match(container.querySelector('[aria-label="Confirmar llegada"]').textContent, /con 4 muestras/)
  await click(button('Confirmar llegada'))
  assert.equal(container.querySelector('h1').textContent, 'Llegada registrada')
  assert.equal(status(), 'Se recibieron 4 muestras en el Laboratorio Central.')
  await click(link('Volver al inicio'))
  assert.match(text(), /Recorrido terminado.*13:40 h/)
})

test('P6 a P9: a bordo agrupa por centro, el fin muestra el balance y la llegada se confirma en una ventana modal', async () => {
  await start()
  await pickUpCenter(71)
  await pickUpCenter(72)
  await go('/transporte/a-bordo')
  assert.deepEqual([...container.querySelectorAll('.transporte-group')].map((row) => row.textContent),
    ['1. Centro DEMO 3 · retirado 10:15 h', '2. Centro DEMO 2 · retirado 10:15 h'])
  await pickUpCenter(73)
  await go('/transporte/a-bordo')
  assert.equal(container.querySelector('h1').textContent, 'Fin del recorrido')
  assert.deepEqual([...container.querySelectorAll('.transporte-balance li')].map((li) => li.textContent),
    ['3 de 3Centros visitados', '4Muestras a entregar', 'Laboratorio CentralLaboratorio Central, Calle 62 N° 555, La Plata'])
  await click(button('Registrar llegada'))
  assert.equal(container.querySelector('[role="dialog"]').getAttribute('aria-label'), 'Confirmar llegada')
  await click(button('Cancelar'))
  assert.ok(!calls.some((call) => call.url.endsWith('/arrival')))
  await click(button('Registrar llegada'))
  await click(button('Confirmar llegada'))
  const receipt = container.querySelector('[aria-label="Llegada confirmada"]')
  assert.deepEqual([...receipt.querySelectorAll('dt')].map((dt) => `${dt.textContent}: ${dt.nextElementSibling.textContent}`),
    ['Hora: 13:40 h', 'Lugar: Laboratorio Central, Calle 62 N° 555, La Plata', 'Muestras: 4', 'Custodia: Transferida al Laboratorio Central'])
})

test('P9: con una sola muestra el comprobante dice "Se recibió 1 muestra"', async () => {
  fake.route.stops = fake.route.stops.slice(0, 1)  // una parada con EST-000004
  await start()
  await pickUpCenter(71)
  await go('/transporte/a-bordo')
  await click(button('Registrar llegada'))
  await click(button('Confirmar llegada'))
  assert.equal(status(), 'Se recibió 1 muestra en el Laboratorio Central.')
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
