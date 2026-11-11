import assert from 'node:assert/strict'
import { after, afterEach, before, beforeEach, mock, test } from 'node:test'
import { Window } from 'happy-dom'
import { createServer } from 'vite'
import React, { act } from 'react'
import { AxiosError } from 'axios'

// El calendario usa la fecha local del navegador: se fija la zona para que la prueba no dependa de la máquina.
process.env.TZ = 'America/Argentina/Buenos_Aires'

let server, Harness, api, setSession, createRoot, root, container, dom, calls, networkDown, slowDay, taken, slotTaken, studyTaken, booked, eligible, myAppointments, cancelRejected
const WEDNESDAY_10 = new Date('2026-11-04T10:00:00-03:00').getTime()
const WEDNESDAY_22 = new Date('2026-11-04T22:00:00-03:00').getTime()
const BEFORE_APPOINTMENT = new Date('2026-11-04T09:00:00-03:00').getTime()
const patient = { access_token: 'test-token', role: 'patient', rol: 'Paciente' }
const doctor = { ...patient, role: 'treating_physician', rol: 'Médico' }
const manager = { ...patient, role: 'medical_manager', rol: 'Gerente' }
const provinces = [{ id: 1, name: 'Provincia Demo', active_centers: 3 }, { id: 2, name: 'Provincia Vacía', active_centers: 0 }, { id: 3, name: 'Provincia Grande', active_centers: 14 }]
const manyCenters = Array.from({ length: 14 }, (_, index) => ({ id: 101 + index, name: `Centro GRANDE ${index + 1}`, address: `Calle Demo ${index + 1}, Ciudad Demo`,
  city: 'Ciudad Demo', province_id: 3, latitude: -34.6 - index / 100, longitude: -58.4, phone: null })).sort((a, b) => (a.name < b.name ? -1 : 1))
// Orden de texto, como lo devuelve el back: "10" antes que "2".
const appointment = { id: 55, study_id: 7, study_code: 'EST-000007', starts_at: '2026-11-04T09:15:00-03:00', status: 'booked',
  center: { id: 10, name: 'Centro DEMO 1', address: 'Calle Demo 100', city: 'Ciudad Demo', phone: '0000-DEMO' } }
const centers = [
  { id: 12, name: 'Centro DEMO 10', address: 'Calle Demo 300, Ciudad Demo', city: 'Ciudad Demo', province_id: 1, latitude: -34.62, longitude: -58.42, phone: null },
  { id: 10, name: 'Centro DEMO 1', address: 'Calle Demo 100, Ciudad Demo', city: 'Ciudad Demo', province_id: 1, latitude: -34.6, longitude: -58.4, phone: null },
  { id: 11, name: 'Centro DEMO 2', address: 'Calle Demo 200, Ciudad Demo', city: 'Ciudad Demo', province_id: 1, latitude: -34.61, longitude: -58.41, phone: null },
]

before(async () => {
  const bootstrap = new Window()
  globalThis.window=bootstrap; globalThis.document=bootstrap.document
  createRoot=(await import('react-dom/client')).createRoot
  bootstrap.close()
  server=await createServer({server:{middlewareMode:true,hmr:false},appType:'custom'})
  Harness=(await server.ssrLoadModule('/tests/harness.jsx')).default
  api=(await server.ssrLoadModule('/src/services/api.js')).api
  setSession=(await server.ssrLoadModule('/src/services/session.js')).setSession
})
after(async () => { await server?.close() })

beforeEach(() => {
  dom=new Window({url:'http://localhost:5173/'})
  globalThis.window=dom;globalThis.document=dom.document;globalThis.HTMLElement=dom.HTMLElement
  globalThis.IS_REACT_ACT_ENVIRONMENT=true
  container=document.createElement('div');document.body.append(container);root=createRoot(container)
  calls=[];networkDown=false;slowDay=null;taken=new Set();slotTaken=false;studyTaken=false;booked=false;cancelRejected=false
  eligible=[{id:7,code:'EST-000007',status:'pagado'}];myAppointments=[]
  mock.timers.enable({apis:['Date'],now:WEDNESDAY_10})
  api.defaults.adapter=async (config) => {
    calls.push({url:config.url,method:config.method,params:config.params,data:config.data&&JSON.parse(config.data)})
    if(networkDown) throw new AxiosError('Network Error','ERR_NETWORK',config)
    let data
    if(config.url==='/provinces') data=provinces
    else if(config.url==='/extraction-centers/10/slots') {
      const date=config.params.date
      if(date===slowDay) await new Promise((resolve)=>setTimeout(resolve,150))
      data={center_id:10,date,business_day:date!=='2026-11-06',holiday:date==='2026-11-06'?'Feriado DEMO':null,
        slots:['2026-11-05','2026-11-06'].includes(date)?[]:[`${date}T09:00:00-03:00`,`${date}T09:15:00-03:00`].filter((slot)=>!taken.has(slot))}
    }
    else if(config.url==='/appointments'&&config.method==='post') {
      const startsAt=JSON.parse(config.data).starts_at
      if(slotTaken||studyTaken) {
        if(slotTaken) taken.add(startsAt); else booked=true  // studyTaken: se reservó desde otra pestaña
        const detail=slotTaken?'El horario ya está reservado en este centro.':'El estudio ya tiene un turno vigente.'
        throw new AxiosError('Request failed with status code 409','ERR_BAD_REQUEST',config,null,{status:409,statusText:'Conflict',headers:{},config,data:{detail}})
      }
      booked=true
      return {data:{...appointment,starts_at:startsAt},status:201,statusText:'Created',headers:{},config}
    }
    else if(config.url==='/studies/7/appointment') {
      if(!booked) {
        const response={status:404,statusText:'Not Found',headers:{},config,data:{detail:'El estudio no tiene un turno vigente.'}}
        throw new AxiosError('Request failed with status code 404','ERR_BAD_REQUEST',config,null,response)
      }
      data=appointment
    }
    else if(config.url==='/appointments/55'&&config.method==='delete') {
      if(cancelRejected) {
        const response={status:409,statusText:'Conflict',headers:{},config,data:{detail:'No se puede cancelar un turno que ya empezó.'}}
        throw new AxiosError('Request failed with status code 409','ERR_BAD_REQUEST',config,null,response)
      }
      booked=false
      return {data:'',status:204,statusText:'No Content',headers:{},config}
    }
    else if(config.url==='/appointments/mine') data=myAppointments
    else if(config.url==='/studies/999/appointment') {
      const response={status:404,statusText:'Not Found',headers:{},config,data:{detail:'El estudio no existe o no es tuyo.'}}
      throw new AxiosError('Request failed with status code 404','ERR_BAD_REQUEST',config,null,response)
    }
    // Como el back: un estudio con turno vigente deja de ser elegible.
    else if(config.url==='/appointments/eligible-studies') data=eligible.filter((study)=>!(booked&&study.id===7))
    else if(config.url==='/extraction-centers') data=[...centers,...manyCenters].filter((c)=>c.province_id===Number(config.params.province_id))
    else if(config.url==='/patients') data={items:[],total:0,offset:0,limit:20}
    else if(['/pathologies','/symptoms'].includes(config.url)) data=[]
    else throw new Error(`Petición inesperada ${config.method} ${config.url}`)
    return {data,status:200,statusText:'OK',headers:{},config}
  }
})
afterEach(async () => { await act(async()=>{root.unmount();setSession(null)});dom.happyDOM.abort();dom.close();mock.timers.reset() })

async function render(path,session=patient) {
  await act(async()=>{setSession(session);root.render(React.createElement(Harness,{initialEntries:[path]}))})
  await settle()
}
async function settle() { await act(async()=>{await new Promise((resolve)=>setTimeout(resolve,320))}) }
async function choose(select,value) {
  await act(async()=>{
    Object.getOwnPropertyDescriptor(dom.HTMLSelectElement.prototype,'value').set.call(select,value)
    select.dispatchEvent(new dom.Event('change',{bubbles:true}))
  })
  await settle()
}
function button(label) {
  const item=[...container.querySelectorAll('button')].find((b)=>b.textContent.trim()===label)
  assert.ok(item,`No se encontró botón ${label}`);return item
}
const RESERVE='/paciente/turnos/reservar?estudio=7'
const province=()=>container.querySelector('#turnos-province')
const centerButtons=()=>[...container.querySelectorAll('button.turnos-center')]
const dayButton=(date)=>container.querySelector(`button[data-date="${date}"]`)
const lastSlotsDate=()=>calls.filter((c)=>c.url.endsWith('/slots')).at(-1)?.params.date
async function pickCenter(path=RESERVE) {
  await render(path)
  await choose(province(),'1')
  await act(async()=>centerButtons()[0].click())
}
async function pickDay(date) { await act(async()=>dayButton(date).click());await settle() }

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
  networkDown=true
  await pickDay('2026-11-04')
  assert.match(container.querySelector('[role="alert"]').textContent,/Revisá la conexión/)
  networkDown=false
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
  slowDay='2026-11-04'
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
  networkDown=true
  await render(RESERVE)
  assert.match(container.querySelector('[role="alert"]').textContent,/Revisá la conexión/)
  networkDown=false
  await act(async()=>button('Reintentar').click());await settle()
  assert.equal(container.querySelector('[role="alert"]'),null)
  assert.ok(province())
})

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
  await act(async()=>root.unmount());root=createRoot(container)
  await render('/paciente/turnos/reservar',manager)
  assert.equal(container.querySelector('h1').textContent,'Catálogo de patologías')
  assert.equal(calls.some((c)=>c.url.startsWith('/extraction-centers')||c.url==='/provinces'),false)
})

test('sin sesión la ruta vuelve al login',async()=>{
  await render('/paciente/turnos/reservar',null)
  assert.equal(container.querySelector('a[href="/paciente/turnos/reservar"]'),null)
  assert.notEqual(container.querySelector('h1')?.textContent,'Reservá tu turno de extracción')
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

const slotButtons=()=>[...container.querySelectorAll('button.turnos-slot')]
async function pickSlot(path,label) {
  await pickCenter(path);await pickDay('2026-11-04')
  await act(async()=>slotButtons().find((b)=>b.textContent===label).click())
}

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
  slotTaken=true
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
  studyTaken=true
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
  networkDown=true
  await render(RESERVE)
  assert.ok(container.querySelector('[role="alert"]'))
  networkDown=false
  await act(async()=>button('Reintentar').click());await settle()
  assert.ok(province(),'aparece el formulario')
})

test('cancelar el turno pide confirmación y vuelve a la reserva del mismo estudio',async()=>{
  mock.timers.setTime(BEFORE_APPOINTMENT)
  booked=true
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
  booked=true
  await render('/paciente/estudios/7/turno')
  networkDown=true
  await act(async()=>button('Cancelar turno').click())
  await act(async()=>button('Sí, cancelar turno').click());await settle()
  assert.ok(container.querySelector('.turnos-appointment [role="alert"]'))
  assert.equal(container.querySelector('h1').textContent,'Día de extracción')
  assert.equal(button('Sí, cancelar turno').disabled,false)
})

for (const [screen,path,loaded] of [
  ['mis turnos','/paciente/turnos',/No tenés turnos reservados/],
  ['la elección de estudio','/paciente/turnos/reservar',/EST-000007/],
  ['el día de extracción','/paciente/estudios/7/turno',/Tu turno/],
]) test(`un error al cargar ${screen} se informa y se puede reintentar`,async()=>{
  booked=path.startsWith('/paciente/estudios')
  networkDown=true
  await render(path)
  assert.ok(container.querySelector('main [role="alert"]'))
  networkDown=false
  await act(async()=>button('Reintentar').click());await settle()
  assert.equal(container.querySelector('main [role="alert"]'),null)
  assert.match(container.textContent,loaded)
})

test('si el back rechaza la cancelación con 409, no la vuelve a ofrecer',async()=>{
  mock.timers.setTime(BEFORE_APPOINTMENT)
  cancelRejected=true
  booked=true
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
  booked=true
  await render('/paciente/estudios/7/turno')  // el turno es a las 9:15 y el reloj marca las 10
  assert.match(container.textContent,/El turno ya empezó: no se puede cancelar/)
  assert.equal([...container.querySelectorAll('button')].some((b)=>b.textContent.includes('Cancelar turno')),false)
})

test('un estudio sin turno vigente lo informa y ofrece reservar',async()=>{
  await render('/paciente/estudios/7/turno')
  assert.match(container.textContent,/Este estudio no tiene un turno vigente/)
  assert.ok(container.querySelector('a[href="/paciente/turnos/reservar?estudio=7"]'))
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
  booked=true
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
  eligible=[]
  await render('/paciente/turnos/reservar')
  assert.match(container.textContent,/No tenés estudios habilitados para sacar turno/)
  assert.ok(container.querySelector('main a[href="/paciente/turnos"]'),'ofrece ver mis turnos')
})

const crumb=()=>container.querySelector('.clinical-breadcrumb').textContent

test('la miga de pan de mis turnos dice Mis turnos',async()=>{
  await render('/paciente/turnos')
  assert.equal(crumb(),'Exoma CareMis turnos')
})

test('la miga de pan del día de extracción cuelga de Mis turnos',async()=>{
  booked=true
  await render('/paciente/estudios/7/turno')
  assert.equal(crumb(),'Exoma CareMis turnosDía de extracción')
  assert.ok(container.querySelector('.clinical-breadcrumb a[href="/paciente/turnos"]'))
})

test('la miga de pan de la reserva sigue diciendo Reservar turno',async()=>{
  await render(RESERVE)
  assert.equal(crumb(),'Exoma CareReservar turno')
})

test('mis turnos lista los turnos con enlace a su día de extracción',async()=>{
  myAppointments=[appointment]
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
