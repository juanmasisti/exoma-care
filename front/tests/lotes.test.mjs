// Lotes (T05): lista por estado y detalle con sus muestras.
import assert from 'node:assert/strict'
import { test } from 'node:test'
import { calls, click, container, crumb, fake, go, render, tab } from './lotes-setup.mjs'

const main = () => container.querySelector('main').textContent

test('la lista abre en los lotes armándose, con su cantidad y un enlace al detalle', async () => {
  await render('/administrativo/lotes')
  assert.equal(container.querySelector('h1').textContent, 'Lotes')
  assert.equal(crumb(), 'Exoma CareLotes')
  assert.equal(tab('Armándose').getAttribute('aria-pressed'), 'true')
  assert.deepEqual(calls.at(-1), { url: '/sample-sets', params: { status: 'assembling' } })
  const card = container.querySelector('.turnos-list').textContent
  assert.match(card, /Lote 4.*Armándose.*9 de 10.*viernes, 20 de noviembre de 2026, 10:30 h/)
  assert.doesNotMatch(card, /Pompe urgente|Cerrado/)
  assert.ok(container.querySelector('main a[href="/administrativo/lotes/4"]'))
})

test('cambiar de pestaña pide ese estado y muestra urgencia y cierre', async () => {
  await render('/administrativo/lotes')
  await click(tab('Cerrados'))
  assert.deepEqual(calls.at(-1), { url: '/sample-sets', params: { status: 'closed' } })
  assert.equal(tab('Cerrados').getAttribute('aria-pressed'), 'true')
  const card = container.querySelector('.turnos-list').textContent
  assert.match(card, /Lote 3.*Cerrado.*Pompe urgente.*4 de 10.*Cerrado.*jueves, 19 de noviembre de 2026, 11:15 h/)
  assert.doesNotMatch(card, /Lote 4/)
})

test('la pestaña sale de la URL, así al volver del detalle se ve la misma', async () => {
  await render('/administrativo/lotes?estado=closed')
  assert.equal(tab('Cerrados').getAttribute('aria-pressed'), 'true')
  assert.match(main(), /Lote 3/)
})

test('un estado sin lotes lo dice, sin decir "Corea"', async () => {
  await render('/administrativo/lotes?estado=in_transit_to_sequencing_lab')
  assert.match(main(), /No hay lotes en «En viaje al laboratorio de secuenciación»/)
  assert.doesNotMatch(container.textContent, /Corea/i)
})

test('un error al cargar la lista se informa y se puede reintentar', async () => {
  fake.networkDown = true
  await render('/administrativo/lotes')
  const alert = container.querySelector('main [role="alert"]')
  assert.ok(alert)
  fake.networkDown = false
  await click(alert.querySelector('button'))
  assert.equal(container.querySelector('main [role="alert"]'), null)
  assert.match(main(), /Lote 4/)
})

test('el detalle muestra estado, urgencia, fechas y las muestras por lugar con el código del estudio', async () => {
  await render('/administrativo/lotes/3')
  assert.equal(container.querySelector('h1').textContent, 'Lote 3')
  assert.equal(crumb(), 'Exoma CareLotesLote 3')
  assert.match(main(), /Cerrado.*Pompe urgente.*4 de 10/)
  const samples = [...container.querySelectorAll('.lotes-samples li')].map((li) => li.textContent)
  assert.deepEqual(samples, ['Lugar 1EST-000021', 'Lugar 2EST-000022', 'Lugar 3EST-000023', 'Lugar 4EST-000024'])
})

test('un lote inexistente lo dice y ofrece volver', async () => {
  await render('/administrativo/lotes/99')
  assert.match(main(), /Este lote no existe/)
  assert.ok(container.querySelector('main a[href="/administrativo/lotes"]'))
})

test('un error al cargar el detalle se informa y se puede reintentar', async () => {
  fake.networkDown = true
  await render('/administrativo/lotes/3')
  fake.networkDown = false
  await click(container.querySelector('main [role="alert"] button'))
  assert.match(main(), /Lugar 1/)
})

test('un lote sin muestras lo dice', async () => {
  await render('/administrativo/lotes/5')
  assert.match(main(), /0 de 10.*El lote todavía no tiene muestras/)
})

test('al pasar de un lote inexistente a otro se ve el nuevo, no el "no existe"', async () => {
  await render('/administrativo/lotes/99')
  assert.match(main(), /Este lote no existe/)
  await go('/administrativo/lotes/3')
  assert.equal(container.querySelector('h1').textContent, 'Lote 3')
  assert.doesNotMatch(main(), /no existe/)
  assert.match(main(), /Lugar 4EST-000024/)
})
