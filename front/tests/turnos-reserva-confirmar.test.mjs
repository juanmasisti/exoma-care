// Reserva: acceso, elección del estudio, confirmar turno y conflictos.
import assert from 'node:assert/strict'
import { test } from 'node:test'
import { act } from 'react'
import { RESERVE, button, calls, centerButtons, choose, container, crumb, doctor, fake, lastSlotsDate, manager, pickDay, pickSlot,
  province, remount, render, settle, slotButtons } from './turnos-setup.mjs'

test('el paciente entra a reservar turno desde su portal',async()=>{
  await render('/portal')
  const link=container.querySelector('a[href="/paciente/turnos/reservar"]')
  assert.ok(link)
  await act(async()=>link.click())
  assert.equal(container.querySelector('h1').textContent,'Reservá tu turno de extracción')
  assert.match(container.querySelector('.clinical-role').textContent,/Paciente/)
  assert.equal(container.querySelector('a[href="/catalogo/patologias"]'),null)
})

test('médico y gerente que entran a la ruta son redirigidos',async()=>{
  await render('/paciente/turnos/reservar',doctor)
  assert.equal(container.querySelector('h1').textContent,'Pacientes')
  await remount()
  await render('/paciente/turnos/reservar',manager)
  assert.equal(container.querySelector('h1').textContent,'Catálogo de patologías')
  assert.equal(calls.some((c)=>c.url.startsWith('/extraction-centers')||c.url==='/provinces'),false)
})

test('sin sesión la ruta vuelve al login',async()=>{
  await render('/paciente/turnos/reservar',null)
  assert.equal(container.querySelector('a[href="/paciente/turnos/reservar"]'),null)
  assert.notEqual(container.querySelector('h1')?.textContent,'Reservá tu turno de extracción')
})

test('confirmar el turno lo reserva y lleva al día de extracción',async()=>{
  await pickSlot(RESERVE,'09:15')
  assert.equal(button('Confirmar turno').disabled,false)
  await act(async()=>button('Confirmar turno').click());await settle()
  assert.deepEqual(calls.find((c)=>c.url==='/appointments').data,{study_id:7,center_id:10,starts_at:'2026-11-04T09:15:00-03:00'})
  assert.equal(container.querySelector('h1').textContent,'Día de extracción')
  const card=container.querySelector('.turnos-appointment').textContent
  assert.match(card,/miércoles, 4 de noviembre de 2026/)
  assert.match(card,/09:15 h/)
  assert.match(card,/Centro DEMO 1Calle Demo 100, Ciudad DemoTeléfono: 0000-DEMO/)
  assert.match(card,/No requiere ayuno ni preparación especial/)
})

test('si el horario se ocupó muestra el mensaje del back y vuelve a pedir los horarios del día',async()=>{
  fake.slotTaken=true
  await pickSlot(RESERVE,'09:15')
  const before=calls.filter((c)=>c.url.endsWith('/slots')).length
  await act(async()=>button('Confirmar turno').click());await settle()
  assert.equal(container.querySelector('.turnos-summary [role="alert"]').textContent,'El horario ya está reservado en este centro.')
  assert.equal(calls.filter((c)=>c.url.endsWith('/slots')).length,before+1)
  assert.equal(lastSlotsDate(),'2026-11-04')
  assert.deepEqual(slotButtons().map((b)=>b.textContent),['09:00'])
  assert.equal(button('Confirmar turno').disabled,true)
  assert.equal(container.querySelector('h1').textContent,'Reservá tu turno de extracción')
})

test('si el estudio ya se reservó desde otra pestaña, el 409 lleva al aviso y no recarga horarios',async()=>{
  fake.studyTaken=true
  await pickSlot(RESERVE,'09:15')
  const before=calls.filter((c)=>c.url.endsWith('/slots')).length
  await act(async()=>button('Confirmar turno').click());await settle()
  assert.match(container.textContent,/Ya tenés un turno para este estudio/)
  assert.ok(container.querySelector('a[href="/paciente/estudios/7/turno"]'))
  assert.equal(calls.filter((c)=>c.url.endsWith('/slots')).length,before)
})

test('un estudio inexistente, ajeno o no habilitado no muestra el formulario',async()=>{
  await render('/paciente/turnos/reservar?estudio=999')
  assert.match(container.textContent,/Este estudio no está habilitado para sacar turno/)
  assert.equal(province(),null)
  assert.ok(container.querySelector('main a[href="/paciente/turnos/reservar"]'))
})

test('un error al revisar el estudio se informa y se puede reintentar',async()=>{
  fake.networkDown=true
  await render(RESERVE)
  assert.ok(container.querySelector('[role="alert"]'))
  fake.networkDown=false
  await act(async()=>button('Reintentar').click());await settle()
  assert.ok(province(),'aparece el formulario')
})

test('un error al cargar la elección de estudio se informa y se puede reintentar',async()=>{
  fake.networkDown=true
  await render('/paciente/turnos/reservar')
  assert.ok(container.querySelector('main [role="alert"]'))
  fake.networkDown=false
  await act(async()=>button('Reintentar').click());await settle()
  assert.equal(container.querySelector('main [role="alert"]'),null)
  assert.match(container.textContent,/EST-000007/)
})

const note=()=>document.getElementById(button('Confirmar turno').getAttribute('aria-describedby'))?.textContent

test('el botón deshabilitado dice qué falta elegir',async()=>{
  await render(RESERVE)
  assert.equal(button('Confirmar turno').disabled,true)
  assert.equal(note(),'Falta elegir el centro.')
  await choose(province(),'1')
  await act(async()=>centerButtons()[0].click())
  assert.equal(note(),'Falta elegir el día.')
  await pickDay('2026-11-04')
  assert.equal(note(),'Falta elegir el horario.')
  await act(async()=>slotButtons()[0].click())
  assert.equal(button('Confirmar turno').disabled,false)
  assert.equal(note(),undefined)
})

test('un estudio que ya tiene turno avisa y lleva a su día de extracción',async()=>{
  fake.booked=true
  await render(RESERVE)
  assert.match(container.textContent,/Ya tenés un turno para este estudio/)
  assert.ok(container.querySelector('a[href="/paciente/estudios/7/turno"]'))
  assert.equal(province(),null)
})

test('sin ?estudio se elige entre los estudios habilitados',async()=>{
  await render('/paciente/turnos/reservar')
  assert.equal(province(),null)
  await act(async()=>button('EST-000007Pagado').click());await settle()
  assert.ok(province(),'aparece el formulario del estudio elegido')
  await pickSlot(RESERVE,'09:15')
  await act(async()=>button('Confirmar turno').click());await settle()
  assert.equal(calls.find((c)=>c.url==='/appointments').data.study_id,7)
})

test('sin estudios habilitados muestra el estado vacío',async()=>{
  fake.eligible=[]
  await render('/paciente/turnos/reservar')
  assert.match(container.textContent,/No tenés estudios habilitados para sacar turno/)
  assert.ok(container.querySelector('main a[href="/paciente/turnos"]'),'ofrece ver mis turnos')
})

test('la miga de pan de la reserva sigue diciendo Reservar turno',async()=>{
  await render(RESERVE)
  assert.equal(crumb(),'Exoma CareReservar turno')
})
