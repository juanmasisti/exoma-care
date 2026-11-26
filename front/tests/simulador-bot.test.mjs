// Simulador del bot de extracción para el administrativo (T03d).
import assert from 'node:assert/strict'
import { test } from 'node:test'
import { act } from 'react'
import { button, calls, choose, container, crumb, dom, fake, labAdmin, patient, remount, render, settle } from './turnos-setup.mjs'

const PATH = '/administrativo/simulador-bot'
const menuItem = () => container.querySelector(`.clinical-navigation a[href="${PATH}"]`)

async function typeVolume(value) {
  const input = container.querySelector('#simulador-volume')
  await act(async () => {
    Object.getOwnPropertyDescriptor(dom.HTMLInputElement.prototype, 'value').set.call(input, value)
    input.dispatchEvent(new dom.Event('input', { bubbles: true }))
  })
}
async function sendNotice(volume) {
  await render(PATH, labAdmin)
  await choose(container.querySelector('#simulador-study'), 'EST-000007')
  await typeVolume(volume)
  await act(async () => button('Enviar aviso').click())
  await settle()
}

test('la pantalla dice SIMULACIÓN, aparece en el menú del administrativo y lista los turnos reservados', async () => {
  await render(PATH, labAdmin)
  assert.equal(container.querySelector('.turnos-heading .turnos-badge').textContent, 'SIMULACIÓN')
  assert.equal(container.querySelector('h1').textContent, 'Simular aviso del bot')
  assert.equal(crumb(), 'Exoma CareSimular aviso del bot')
  assert.equal(menuItem().className, 'clinical-nav-active')
  const options = [...container.querySelectorAll('#simulador-study option')].map((option) => option.textContent)
  assert.match(options[1], /EST-000007 · Paciente DEMO · Centro DEMO 1/)
  assert.equal(button('Enviar aviso').disabled, true)
})

test('con poco volumen dice que hay que repetir la extracción y saca el estudio de la lista', async () => {
  await sendNotice('1.9')
  assert.deepEqual(calls.find((call) => call.method === 'post').data, { study_code: 'EST-000007', volume_ml: '1.9' })
  assert.match(container.querySelector('[role="status"]').textContent, /Hay que repetir la extracción.*EST-000007/)
  assert.match(container.textContent, /No hay turnos reservados esperando el aviso/)
})

test('con volumen suficiente dice que la muestra quedó lista para retirar', async () => {
  await sendNotice('2.5')
  assert.match(container.querySelector('[role="status"]').textContent, /Muestra lista para retirar/)
})

test('un rechazo del back se muestra y no hay resultado', async () => {
  fake.simulateRejected = true
  await sendNotice('2.5')
  assert.equal(container.querySelector('main [role="alert"]').textContent, 'El estudio no está esperando una extracción.')
  assert.equal(container.querySelector('main [role="status"]'), null)
})

test('un error al cargar la lista se informa y se puede reintentar', async () => {
  fake.networkDown = true
  await render(PATH, labAdmin)
  const retry = container.querySelector('main [role="alert"] button')
  fake.networkDown = false
  await act(async () => retry.click()); await settle()
  assert.ok(container.querySelector('#simulador-study'))
})

test('con el simulador apagado el menú no lo muestra y la pantalla lo explica', async () => {
  fake.demoEnabled = false
  // Otra sesión: el menú pregunta una vez por sesión y las pruebas anteriores lo vieron prendido.
  await render(PATH, { ...labAdmin, access_token: 'otra-sesion' })
  assert.equal(menuItem(), null)
  assert.equal(container.querySelector('main [role="alert"]').textContent, 'El simulador está apagado en este servidor.')
})

test('el menú pregunta una sola vez por sesión', async () => {
  const session = { ...labAdmin, access_token: 'sesion-nueva' }
  const lists = () => calls.filter((call) => call.url === '/demo/extraction-notice/studies').length
  await render(PATH, session)
  assert.equal(lists(), 2)  // la del menú y la de la pantalla
  await remount(); await render(PATH, session)
  assert.equal(lists(), 3)  // el menú nuevo usa la respuesta guardada: solo consulta la pantalla
  assert.ok(menuItem())
})

test('otros roles no ven el simulador ni consultan si está prendido', async () => {
  await render('/paciente/turnos', patient)
  assert.equal(menuItem(), null)
  assert.equal(calls.some((call) => call.url.startsWith('/demo/')), false)
})
