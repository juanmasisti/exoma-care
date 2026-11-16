// Mis turnos: lista, estado vacío, menú y miga de pan.
import assert from 'node:assert/strict'
import { test } from 'node:test'
import { act } from 'react'
import { appointment, container, crumb, fake, render, settle } from './turnos-setup.mjs'

test('un error al cargar mis turnos se informa y se puede reintentar',async()=>{
  fake.networkDown=true
  await render('/paciente/turnos')
  // Turnos y seguimiento cargan por separado: cada uno avisa su error y tiene su Reintentar.
  const retries=[...container.querySelectorAll('main [role="alert"] button')]
  assert.equal(retries.length,2)
  fake.networkDown=false
  for(const retry of retries) await act(async()=>retry.click())
  await settle()
  assert.equal(container.querySelector('main [role="alert"]'),null)
  assert.match(container.textContent,/No tenés turnos reservados/)
})

test('la miga de pan de mis turnos dice Mis turnos',async()=>{
  await render('/paciente/turnos')
  assert.equal(crumb(),'Exoma CareMis turnos')
})

test('mis turnos lista los turnos con enlace a su día de extracción',async()=>{
  fake.myAppointments=[appointment]
  await render('/paciente/turnos')
  assert.equal(container.querySelector('h1').textContent,'Mis turnos')
  const card=container.querySelector('.turnos-list').textContent
  assert.match(card,/Estudio EST-000007/)
  assert.match(card,/miércoles, 4 de noviembre de 2026/)
  assert.match(card,/09:15 h/)
  assert.ok(container.querySelector('.turnos-list a[href="/paciente/estudios/7/turno"]'))
})

test('mis turnos sin turnos ofrece reservar',async()=>{
  await render('/paciente/turnos')
  assert.match(container.textContent,/No tenés turnos reservados/)
  assert.ok(container.querySelector('main a[href="/paciente/turnos/reservar"]'))
})

test('el menú del paciente tiene Mis turnos y marca solo la pantalla actual',async()=>{
  await render('/paciente/turnos')
  const nav=container.querySelector('.clinical-navigation')
  assert.equal(nav.querySelector('a[href="/paciente/turnos"]').className,'clinical-nav-active')
  assert.equal(nav.querySelector('a[href="/paciente/turnos/reservar"]').className,'clinical-nav-link')
  await act(async()=>nav.querySelector('a[href="/paciente/turnos/reservar"]').click());await settle()
  // La pantalla nueva monta su propio menú: se vuelve a buscar.
  const current=container.querySelector('.clinical-navigation')
  assert.equal(current.querySelector('a[href="/paciente/turnos"]').className,'clinical-nav-link')
  assert.equal(current.querySelector('a[href="/paciente/turnos/reservar"]').className,'clinical-nav-active')
})
