// Base de transporte, lotes y envío (decisión 016): rutas, menú y pantallas "En construcción".
// Las pantallas de lotes ya las prueba lotes.test.mjs (T05) y las de transporte transportista-*.test.mjs (T04).
import assert from 'node:assert/strict'
import { test } from 'node:test'
import { container, labAdmin, patient, render } from './turnos-setup.mjs'

const menuItem = (path) => container.querySelector(`.clinical-navigation a[href="${path}"]`)

test('el administrativo ve órdenes, lotes y el recorrido (provisorio) en el menú', async () => {
  await render('/administrativo/lotes', labAdmin)
  assert.equal(menuItem('/administrativo/lotes').className, 'clinical-nav-active')
  assert.ok(menuItem('/administrativo/ordenes-del-dia'))
  assert.match(menuItem('/transporte').textContent, /Recorrido del día.*PROVISORIO/)
})

test('el paciente no ve los ítems ni entra a las pantallas de logística', async () => {
  for (const path of ['/transporte', '/administrativo/lotes', '/administrativo/ordenes-del-dia']) {
    await render(path, patient)
    assert.notEqual(container.querySelector('h1')?.textContent, 'Lotes')
    assert.doesNotMatch(container.textContent, /En construcción/)
    assert.equal(menuItem('/transporte'), null)
    assert.equal(menuItem('/administrativo/lotes'), null)
  }
})
