// Reserva: provincia, centros, mapa, calendario y horarios.
import assert from 'node:assert/strict'
import { mock, test } from 'node:test'
import React, { act } from 'react'
import { Harness, RESERVE, WEDNESDAY_22, button, calls, centerButtons, choose, container, dayButton, dom, fake, lastSlotsDate,
  patient, pickCenter, pickDay, province, render, root, setSession, settle } from './turnos-setup.mjs'

test('el calendario se titula con el mes y no deja elegir fines de semana ni días pasados',async()=>{
  await pickCenter()
  assert.equal(container.querySelector('.turnos-calendar-header strong').textContent,'Noviembre de 2026')
  assert.equal(dayButton('2026-11-03').disabled,true)
  assert.equal(dayButton('2026-11-07').disabled,true)
  assert.equal(dayButton('2026-11-08').disabled,true)
  assert.equal(dayButton('2026-11-04').disabled,false)
  assert.equal(dayButton('2026-11-30').disabled,false)
  assert.equal(container.querySelector('button[aria-label="Mes anterior"]').disabled,true)
})

test('un día sin turnos lo informa',async()=>{
  await pickCenter();await pickDay('2026-11-05')
  assert.match(container.textContent,/No hay turnos libres/)
  assert.equal(container.querySelectorAll('button.turnos-slot').length,0)
})

test('un feriado muestra su descripción',async()=>{
  await pickCenter();await pickDay('2026-11-06')
  assert.match(container.textContent,/Feriado: Feriado DEMO/)
})

test('a las 22 se pide el día del calendario, no el siguiente',async()=>{
  mock.timers.setTime(WEDNESDAY_22)
  await pickCenter();await pickDay('2026-11-04')
  assert.equal(lastSlotsDate(),'2026-11-04')
  assert.equal(dayButton('2026-11-04').disabled,false)
})

test('un error al pedir horarios se informa y se puede reintentar',async()=>{
  await pickCenter()
  fake.networkDown=true
  await pickDay('2026-11-04')
  assert.match(container.querySelector('[role="alert"]').textContent,/Revisá la conexión/)
  fake.networkDown=false
  await act(async()=>button('Reintentar').click());await settle()
  assert.equal(container.querySelector('[role="alert"]'),null)
  assert.deepEqual([...container.querySelectorAll('button.turnos-slot')].map((b)=>b.textContent),['09:00','09:15'])
})

test('pasada la medianoche el día anterior queda deshabilitado',async()=>{
  mock.timers.setTime(new Date('2026-11-04T23:59:00-03:00').getTime())
  await pickCenter()
  assert.equal(dayButton('2026-11-04').disabled,false)
  mock.timers.setTime(new Date('2026-11-05T00:01:00-03:00').getTime())
  await pickDay('2026-11-05')
  assert.equal(dayButton('2026-11-04').disabled,true)
})

test('una respuesta vieja no pisa los horarios del día nuevo',async()=>{
  fake.slowDay='2026-11-04'
  await pickCenter()
  await act(async()=>dayButton('2026-11-04').click())
  await pickDay('2026-11-05')
  assert.match(container.textContent,/No hay turnos libres/)
  assert.equal(container.querySelectorAll('button.turnos-slot').length,0)
})

test('el paciente elige centro, día y horario y ve su selección',async()=>{
  await pickCenter();await pickDay('2026-11-04')
  assert.equal(dayButton('2026-11-04').getAttribute('aria-label'),'miércoles, 4 de noviembre')
  assert.ok(container.querySelector('[aria-live="polite"] .turnos-slots'))
  const slots=[...container.querySelectorAll('button.turnos-slot')]
  assert.deepEqual(slots.map((b)=>b.textContent),['09:00','09:15'])
  await act(async()=>slots[1].click())
  const summary=container.querySelector('.turnos-summary').textContent
  assert.match(summary,/Centro DEMO 1Calle Demo 100, Ciudad Demo/)
  assert.match(summary,/miércoles, 4 de noviembre de 2026/)
  assert.match(summary,/09:15 h/)
  assert.equal(button('Confirmar turno').disabled,false)
})

test('elegir provincia muestra los centros en orden numérico como botones elegibles',async()=>{
  await render(RESERVE)
  assert.match(province().textContent,/Provincia Demo \(3 centros\)/)
  await choose(province(),'1')
  assert.equal(calls.find((c)=>c.url==='/extraction-centers').params.province_id,'1')
  assert.deepEqual(centerButtons().map((b)=>b.textContent),
    ['Centro DEMO 1Calle Demo 100, Ciudad Demo','Centro DEMO 2Calle Demo 200, Ciudad Demo','Centro DEMO 10Calle Demo 300, Ciudad Demo'])
  assert.ok(centerButtons().every((b)=>b.getAttribute('aria-pressed')==='false'))
  await act(async()=>centerButtons()[1].click())
  assert.deepEqual(centerButtons().map((b)=>b.getAttribute('aria-pressed')),['false','true','false'])
})

test('el mapa muestra un marcador por centro y elegir uno marca su tarjeta',async()=>{
  // StrictMode, como main.jsx: monta los efectos dos veces y el mapa no debe crearse dos veces.
  await act(async()=>{setSession(patient);root.render(React.createElement(React.StrictMode,null,React.createElement(Harness,{initialEntries:[RESERVE]})))})
  await settle()
  await choose(province(),'1')
  assert.doesNotMatch(container.textContent,/No se pudo cargar el mapa/)
  const map=container.querySelector('.turnos-map')
  const markers=[...map.querySelectorAll('path.leaflet-interactive')]
  assert.equal(markers.length,3)
  assert.match(map.textContent,/OpenStreetMap/)
  await act(async()=>markers[1].dispatchEvent(new dom.MouseEvent('click',{bubbles:true})))
  assert.deepEqual(centerButtons().map((b)=>b.getAttribute('aria-pressed')),['false','true','false'])
})

const centerNames=()=>centerButtons().map((b)=>b.querySelector('strong').textContent.replace('Centro GRANDE ',''))
const range=(from,to)=>Array.from({length:to-from+1},(_,i)=>String(from+i))

test('se ven 8 centros por defecto y la página siguiente muestra los otros',async()=>{
  await render(RESERVE)
  await choose(province(),'3')
  assert.deepEqual(centerNames(),range(1,8))
  assert.match(container.querySelector('.patients-pagination').textContent,/1–8 de 14 centros/)
  assert.equal(button('Anterior').disabled,true)
  await act(async()=>button('Siguiente').click())
  assert.deepEqual(centerNames(),range(9,14))
  assert.equal(button('Siguiente').disabled,true)
  // Cambiar de provincia vuelve a la página 1; con 3 centros no hay paginación ni selector.
  await choose(province(),'1')
  assert.equal(container.querySelector('.patients-pagination'),null)
  assert.equal(container.querySelector('#turnos-page-size'),null)
  await choose(province(),'3')
  assert.deepEqual(centerNames(),range(1,8))
})

test('cambiar a 12 muestra 12 y vuelve a la página 1; con Todos no hay botones de página',async()=>{
  await render(RESERVE)
  await choose(province(),'3')
  await act(async()=>button('Siguiente').click())
  await choose(container.querySelector('#turnos-page-size'),'12')
  assert.deepEqual(centerNames(),range(1,12))
  assert.match(container.querySelector('.patients-pagination').textContent,/1–12 de 14 centros/)
  await choose(container.querySelector('#turnos-page-size'),'0')
  assert.deepEqual(centerNames(),range(1,14))
  assert.equal(container.querySelector('.patients-pagination'),null)
})

test('elegir desde el mapa un centro de otra página lo muestra elegido',async()=>{
  await render(RESERVE)
  await choose(province(),'3')
  const markers=[...container.querySelectorAll('.turnos-map path.leaflet-interactive')]
  assert.equal(markers.length,14)
  await act(async()=>markers[9].dispatchEvent(new dom.MouseEvent('click',{bubbles:true})))
  assert.deepEqual(centerNames(),range(9,14))
  assert.equal(container.querySelector('button.turnos-center[aria-pressed="true"] strong').textContent,'Centro GRANDE 10')
})

test('una provincia sin centros muestra el estado vacío',async()=>{
  await render(RESERVE)
  await choose(province(),'2')
  assert.match(container.textContent,/No hay centros activos en esta provincia/)
  assert.equal(centerButtons().length,0)
})

test('un error de red se informa y se puede reintentar',async()=>{
  fake.networkDown=true
  await render(RESERVE)
  assert.match(container.querySelector('[role="alert"]').textContent,/Revisá la conexión/)
  fake.networkDown=false
  await act(async()=>button('Reintentar').click());await settle()
  assert.equal(container.querySelector('[role="alert"]'),null)
  assert.ok(province())
})

test('volver a elegir el mismo día recarga horarios sin quedar en carga permanente',async()=>{
  await pickCenter();await pickDay('2026-11-04')
  const firstRequests=calls.filter(c=>c.url.endsWith('/slots')).length
  assert.equal(container.querySelectorAll('button.turnos-slot').length,2)
  await pickDay('2026-11-04')
  assert.equal(container.querySelectorAll('button.turnos-slot').length,2)
  assert.equal(calls.filter(c=>c.url.endsWith('/slots')).length,firstRequests+1)
  assert.doesNotMatch(container.textContent,/Cargando horarios/)
})
