// Día de extracción: tarjeta del turno y cancelación.
import assert from 'node:assert/strict'
import { mock, test } from 'node:test'
import { act } from 'react'
import { BEFORE_APPOINTMENT, button, calls, container, crumb, fake, province, render, settle } from './turnos-setup.mjs'

test('cancelar el turno pide confirmación y vuelve a la reserva del mismo estudio',async()=>{
  mock.timers.setTime(BEFORE_APPOINTMENT)
  fake.booked=true
  await render('/paciente/estudios/7/turno')
  await act(async()=>button('Cancelar turno').click())
  assert.match(container.textContent,/¿Querés cancelar este turno\?/)
  await act(async()=>button('No, mantener turno').click())
  assert.equal(calls.some((c)=>c.method==='delete'),false)
  await act(async()=>button('Cancelar turno').click())
  await act(async()=>button('Sí, cancelar turno').click());await settle()
  assert.ok(calls.some((c)=>c.method==='delete'&&c.url==='/appointments/55'))
  assert.equal(container.querySelector('h1').textContent,'Reservá tu turno de extracción')
  assert.ok(province(),'vuelve al formulario del mismo estudio')
})

test('un error al cancelar se informa y el turno sigue a la vista',async()=>{
  mock.timers.setTime(BEFORE_APPOINTMENT)
  fake.booked=true
  await render('/paciente/estudios/7/turno')
  fake.networkDown=true
  await act(async()=>button('Cancelar turno').click())
  await act(async()=>button('Sí, cancelar turno').click());await settle()
  assert.ok(container.querySelector('.turnos-appointment [role="alert"]'))
  assert.equal(container.querySelector('h1').textContent,'Día de extracción')
  assert.equal(button('Sí, cancelar turno').disabled,false)
})

test('un error al cargar el día de extracción se informa y se puede reintentar',async()=>{
  fake.booked=true
  fake.networkDown=true
  await render('/paciente/estudios/7/turno')
  assert.ok(container.querySelector('main [role="alert"]'))
  fake.networkDown=false
  await act(async()=>button('Reintentar').click());await settle()
  assert.equal(container.querySelector('main [role="alert"]'),null)
  assert.match(container.textContent,/Tu turno/)
})

test('si el back rechaza la cancelación con 409, no la vuelve a ofrecer',async()=>{
  mock.timers.setTime(BEFORE_APPOINTMENT)
  fake.cancelRejected=true
  fake.booked=true
  await render('/paciente/estudios/7/turno')
  await act(async()=>button('Cancelar turno').click())
  mock.timers.setTime(new Date('2026-11-04T09:16:00-03:00').getTime())  // confirma después de la hora del turno
  await act(async()=>button('Sí, cancelar turno').click());await settle()
  assert.equal(container.querySelector('.turnos-appointment [role="alert"]').textContent,'No se puede cancelar un turno que ya empezó.')
  assert.equal(container.querySelector('.turnos-confirm'),null)
  assert.match(container.textContent,/El turno ya empezó: no se puede cancelar/)
  assert.equal(calls.filter((c)=>c.url==='/studies/7/appointment').length,2)
})

test('un turno que ya empezó no ofrece cancelar',async()=>{
  fake.booked=true
  await render('/paciente/estudios/7/turno')  // el turno es a las 9:15 y el reloj marca las 10
  assert.match(container.textContent,/El turno ya empezó: no se puede cancelar/)
  assert.equal([...container.querySelectorAll('button')].some((b)=>b.textContent.includes('Cancelar turno')),false)
})

test('un estudio sin turno vigente lo informa y ofrece reservar',async()=>{
  await render('/paciente/estudios/7/turno')
  assert.match(container.textContent,/Este estudio no tiene un turno vigente/)
  assert.ok(container.querySelector('a[href="/paciente/turnos/reservar?estudio=7"]'))
})

test('la miga de pan del día de extracción cuelga de Mis turnos',async()=>{
  fake.booked=true
  await render('/paciente/estudios/7/turno')
  assert.equal(crumb(),'Exoma CareMis turnosDía de extracción')
  assert.ok(container.querySelector('.clinical-breadcrumb a[href="/paciente/turnos"]'))
})
