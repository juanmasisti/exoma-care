// Seguimiento del estudio: etapas, remuestreo, errores y cómo se llega desde Mis turnos y Día de extracción.
import assert from 'node:assert/strict'
import { test } from 'node:test'
import { act } from 'react'
import { appointment, button, calls, container, crumb, discardedSample, fake, render, settle, tracking } from './turnos-setup.mjs'

const TRACKING = '/paciente/estudios/7/seguimiento'
const title = () => container.querySelector('main h2').textContent
const currentStage = () => container.querySelector('.turnos-stages [aria-current="step"]')
const newBookingLink = () => container.querySelector('a[href="/paciente/turnos/reservar?estudio=7"]')
async function follow(link) { await act(async()=>link.click());await settle() }

for (const [stage, text] of [
  ['extraction', 'Extracción'], ['ready_for_pickup', 'Muestra lista para retirar'], ['to_lab', 'En camino al laboratorio'],
  ['central_lab', 'En el laboratorio central'], ['to_korea', 'En viaje al laboratorio de análisis'],
  ['analysis', 'En análisis'], ['result_available', 'Resultado disponible'],
]) {
  test(`la etapa ${stage} se muestra como "${text}" y sin botón de turno nuevo`,async()=>{
    fake.tracking=tracking(stage)
    await render(TRACKING)
    assert.equal(title(),`Estudio EST-000007: ${text}`)
    assert.equal(currentStage().querySelector('strong').textContent,text)
    assert.equal(newBookingLink(),null)
  })
}

test('las etapas anteriores quedan hechas y las siguientes, por venir, también para lector de pantalla',async()=>{
  fake.tracking=tracking('central_lab')
  await render(TRACKING)
  const items=[...container.querySelectorAll('.turnos-stages li')]
  assert.deepEqual(items.map((item)=>item.className),['done','done','done','current','pending','pending','pending'])
  assert.deepEqual(items.map((item)=>item.querySelector('.turnos-sr-only')?.textContent ?? null),
    [' (hecha)',' (hecha)',' (hecha)',null,' (por venir)',' (por venir)',' (por venir)'])
})

test('una etapa que el front no conoce se muestra como En proceso',async()=>{
  fake.tracking=tracking('otra_etapa')
  await render(TRACKING)
  assert.equal(title(),'Estudio EST-000007: En proceso')
})

test('sin muestra todavía, lo dice en palabras simples',async()=>{
  await render(TRACKING)
  assert.match(currentStage().textContent,/Todavía no recibimos tu muestra. Se toma el día de tu turno de extracción/)
  assert.equal(container.querySelector('.turnos-history'),null)
})

test('en remuestreo por volumen explica que hay que repetir la extracción y ofrece el turno nuevo',async()=>{
  fake.tracking=tracking('resample',[discardedSample()],'requiere_remuestreo')
  await render(TRACKING)
  assert.equal(title(),'Estudio EST-000007: Hay que repetir la extracción')
  assert.match(container.textContent,/no tenés que pagar de nuevo/)
  assert.match(container.textContent,/Motivo: La muestra no alcanzó el volumen mínimo de 2 ml/)
  assert.equal(newBookingLink().textContent,'Sacar turno nuevo')
  assert.equal(container.querySelector('.turnos-stages'),null)
  assert.match(container.querySelector('.turnos-history').textContent,/miércoles, 4 de noviembre de 2026: 1,90 ml, descartada/)
})

test('en remuestreo pedido por bioinformática muestra su motivo',async()=>{
  fake.tracking=tracking('resample',[discardedSample('ADN insuficiente')],'requiere_remuestreo')
  await render(TRACKING)
  assert.match(container.textContent,/Motivo: ADN insuficiente/)
})

test('"Sacar turno nuevo" lleva a reservar con ese estudio elegido',async()=>{
  fake.tracking=tracking('resample',[discardedSample()],'requiere_remuestreo')
  fake.eligible=[{id:7,code:'EST-000007',status:'requiere_remuestreo'}]
  await render(TRACKING)
  await follow(newBookingLink())
  assert.equal(container.querySelector('h1').textContent,'Reservá tu turno de extracción')
  assert.ok(container.querySelector('#turnos-centers-title'))  // ya en el paso del centro: no pide elegir estudio
  assert.equal(container.querySelector('#turnos-study-title'),null)
})

test('la lista para reservar nombra el estado de remuestreo',async()=>{
  fake.eligible=[{id:7,code:'EST-000007',status:'requiere_remuestreo'}]
  await render('/paciente/turnos/reservar')
  assert.match(container.textContent,/Requiere nueva extracción/)
})

test('con el turno nuevo ya sacado vuelve a esperar la extracción y conserva el historial',async()=>{
  fake.tracking=tracking('extraction',[discardedSample()])
  await render(TRACKING)
  assert.equal(title(),'Estudio EST-000007: Extracción')
  assert.equal(newBookingLink(),null)
  assert.ok(container.querySelector('.turnos-history'))
})

test('un error al cargar el seguimiento se informa y se puede reintentar',async()=>{
  fake.networkDown=true
  await render(TRACKING)
  assert.ok(container.querySelector('main [role="alert"]'))
  fake.networkDown=false
  await act(async()=>button('Reintentar').click());await settle()
  assert.equal(container.querySelector('main [role="alert"]'),null)
  assert.equal(title(),'Estudio EST-000007: Extracción')
  assert.equal(calls.filter((c)=>c.url==='/studies/7/tracking').length,2)
})

test('la miga de pan del seguimiento cuelga de Mis turnos',async()=>{
  await render(TRACKING)
  assert.equal(crumb(),'Exoma CareMis turnosSeguimiento')
})

test('desde Mis turnos se llega al seguimiento de un estudio ya extraído',async()=>{
  fake.myTrackings=[{study_id:7,code:'EST-000007',status:'requiere_remuestreo',stage:'resample',requires_new_extraction:true}]
  fake.tracking=tracking('resample',[discardedSample()],'requiere_remuestreo')
  await render('/paciente/turnos')
  const section=container.querySelector('.turnos-tracked')
  assert.match(section.textContent,/Estudio EST-000007Hay que repetir la extracción/)
  await follow(section.querySelector(`a[href="${TRACKING}"]`))
  assert.equal(container.querySelector('h1').textContent,'Seguimiento')
})

test('si falla solo el seguimiento, Mis turnos sigue mostrando los turnos y se puede reintentar',async()=>{
  fake.myAppointments=[appointment]
  fake.myTrackingsDown=true
  await render('/paciente/turnos')
  assert.match(container.querySelector('.turnos-list').textContent,/Estudio EST-000007/)
  assert.equal(container.querySelector('[role="alert"]').textContent,'No se pudo cargar el seguimiento.Reintentar')
  fake.myTrackingsDown=false
  fake.myTrackings=[{study_id:8,code:'EST-000008',status:'listo_para_retirar',stage:'ready_for_pickup',requires_new_extraction:false}]
  await act(async()=>button('Reintentar').click());await settle()
  assert.equal(container.querySelector('[role="alert"]'),null)
  assert.match(container.querySelector('.turnos-tracked').textContent,/Muestra lista para retirar/)
})

test('sin turnos pero con estudios en seguimiento no invita a reservar',async()=>{
  fake.myTrackings=[{study_id:7,code:'EST-000007',status:'listo_para_retirar',stage:'ready_for_pickup',requires_new_extraction:false}]
  await render('/paciente/turnos')
  assert.doesNotMatch(container.textContent,/No tenés turnos reservados/)
  assert.ok(container.querySelector('.turnos-tracked'))
})

test('un estudio con turno reservado y muestra anterior tiene una sola tarjeta, con su etapa',async()=>{
  fake.myAppointments=[appointment]
  fake.myTrackings=[{study_id:7,code:'EST-000007',status:'turno_sacado',stage:'extraction',requires_new_extraction:false},
    {study_id:8,code:'EST-000008',status:'requiere_remuestreo',stage:'resample',requires_new_extraction:true}]
  await render('/paciente/turnos')
  assert.equal(container.querySelectorAll('.turnos-list li.turnos-card').length,2)
  assert.equal(container.querySelector('.turnos-list .turnos-minibar').getAttribute('aria-label'),'Etapa 1 de 7: Extracción')
  const tracked=container.querySelector('.turnos-tracked')
  assert.doesNotMatch(tracked.textContent,/EST-000007/)
  assert.ok(tracked.querySelector('a.turnos-action[href="/paciente/turnos/reservar?estudio=8"]'))
})

test('cada turno de Mis turnos enlaza a su seguimiento',async()=>{
  fake.myAppointments=[appointment]
  await render('/paciente/turnos')
  assert.ok(container.querySelector(`.turnos-list a[href="${TRACKING}"]`))
  assert.equal(container.querySelector('.turnos-tracked'),null)  // sin estudios extraídos no hay sección
})

test('desde Día de extracción se llega al seguimiento, con o sin turno vigente',async()=>{
  fake.booked=true
  await render('/paciente/estudios/7/turno')
  await follow(container.querySelector(`a[href="${TRACKING}"]`))
  assert.equal(container.querySelector('h1').textContent,'Seguimiento')
})

test('Día de extracción sin turno vigente también ofrece el seguimiento',async()=>{
  await render('/paciente/estudios/7/turno')
  assert.match(container.textContent,/Este estudio no tiene un turno vigente/)
  assert.ok(container.querySelector(`a[href="${TRACKING}"]`))
})
