// Base de transporte, lotes y envío (decisión 016): rutas, menú y pantallas "En construcción".
// Las pantallas de lotes ya las prueba lotes.test.mjs (T05).
import assert from 'node:assert/strict'
import { test } from 'node:test'
import { container, crumb, labAdmin, patient, render } from './turnos-setup.mjs'

const menuItem = (path) => container.querySelector(`.clinical-navigation a[href="${path}"]`)

for (const [path, title, crumbText] of [
  ['/administrativo/ordenes-del-dia', 'Órdenes del día', 'Exoma CareÓrdenes del día'],
  ['/transporte', 'Recorrido del día', 'Exoma CareRecorrido del día'],
]) {
  test(`${path} está en construcción para el administrativo`, async () => {
    await render(path, labAdmin)
    assert.equal(container.querySelector('h1').textContent, title)
    assert.match(container.querySelector('main').textContent, /En construcción/)
    assert.equal(crumb(), crumbText)
  })
}

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
