// Armado común de las pruebas de turnos: DOM, sesión, doble de la API y helpers de interacción.
import assert from 'node:assert/strict'
import { after, afterEach, before, beforeEach, mock } from 'node:test'
import { Window } from 'happy-dom'
import { createServer } from 'vite'
import React, { act } from 'react'
import { AxiosError } from 'axios'

// El calendario usa la fecha local del navegador: se fija la zona para que la prueba no dependa de la máquina.
process.env.TZ = 'America/Argentina/Buenos_Aires'

let server, api, createRoot
export let Harness, setSession, root, container, dom, calls
// Estado del doble de la API; cada prueba lo ajusta antes de renderizar.
export const fake = {}
export const WEDNESDAY_10 = new Date('2026-11-04T10:00:00-03:00').getTime()
export const WEDNESDAY_22 = new Date('2026-11-04T22:00:00-03:00').getTime()
export const BEFORE_APPOINTMENT = new Date('2026-11-04T09:00:00-03:00').getTime()
export const patient = { access_token: 'test-token', role: 'patient', rol: 'Paciente' }
export const doctor = { ...patient, role: 'treating_physician', rol: 'Médico' }
export const manager = { ...patient, role: 'medical_manager', rol: 'Gerente' }
const provinces = [{ id: 1, name: 'Provincia Demo', active_centers: 3 }, { id: 2, name: 'Provincia Vacía', active_centers: 0 }, { id: 3, name: 'Provincia Grande', active_centers: 14 }]
const manyCenters = Array.from({ length: 14 }, (_, index) => ({ id: 101 + index, name: `Centro GRANDE ${index + 1}`, address: `Calle Demo ${index + 1}, Ciudad Demo`,
  city: 'Ciudad Demo', province_id: 3, latitude: -34.6 - index / 100, longitude: -58.4, phone: null })).sort((a, b) => (a.name < b.name ? -1 : 1))
// Orden de texto, como lo devuelve el back: "10" antes que "2".
export const appointment = { id: 55, study_id: 7, study_code: 'EST-000007', starts_at: '2026-11-04T09:15:00-03:00', status: 'booked',
  center: { id: 10, name: 'Centro DEMO 1', address: 'Calle Demo 100', city: 'Ciudad Demo', phone: '0000-DEMO' } }
const centers = [
  { id: 12, name: 'Centro DEMO 10', address: 'Calle Demo 300, Ciudad Demo', city: 'Ciudad Demo', province_id: 1, latitude: -34.62, longitude: -58.42, phone: null },
  { id: 10, name: 'Centro DEMO 1', address: 'Calle Demo 100, Ciudad Demo', city: 'Ciudad Demo', province_id: 1, latitude: -34.6, longitude: -58.4, phone: null },
  { id: 11, name: 'Centro DEMO 2', address: 'Calle Demo 200, Ciudad Demo', city: 'Ciudad Demo', province_id: 1, latitude: -34.61, longitude: -58.41, phone: null },
]

function failure(config, status, statusText, detail) {
  return new AxiosError(`Request failed with status code ${status}`, 'ERR_BAD_REQUEST', config, null, { status, statusText, headers: {}, config, data: { detail } })
}

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
  calls=[]
  Object.assign(fake,{networkDown:false,slowDay:null,taken:new Set(),slotTaken:false,studyTaken:false,booked:false,cancelRejected:false,documentRejected:false,
    eligible:[{id:7,code:'EST-000007',status:'pagado'}],myAppointments:[]})
  mock.timers.enable({apis:['Date'],now:WEDNESDAY_10})
  api.defaults.adapter=async (config) => {
    calls.push({url:config.url,method:config.method,params:config.params,data:config.data&&JSON.parse(config.data),responseType:config.responseType,authorization:config.headers?.Authorization})
    if(fake.networkDown) throw new AxiosError('Network Error','ERR_NETWORK',config)
    let data
    if(config.url==='/provinces') data=provinces
    else if(config.url==='/extraction-centers/10/slots') {
      const date=config.params.date
      if(date===fake.slowDay) await new Promise((resolve)=>setTimeout(resolve,150))
      data={center_id:10,date,business_day:date!=='2026-11-06',holiday:date==='2026-11-06'?'Feriado DEMO':null,
        slots:['2026-11-05','2026-11-06'].includes(date)?[]:[`${date}T09:00:00-03:00`,`${date}T09:15:00-03:00`].filter((slot)=>!fake.taken.has(slot))}
    }
    else if(config.url==='/appointments'&&config.method==='post') {
      const startsAt=JSON.parse(config.data).starts_at
      if(fake.slotTaken||fake.studyTaken) {
        if(fake.slotTaken) fake.taken.add(startsAt); else fake.booked=true  // studyTaken: se reservó desde otra pestaña
        throw failure(config,409,'Conflict',fake.slotTaken?'El horario ya está reservado en este centro.':'El estudio ya tiene un turno vigente.')
      }
      fake.booked=true
      return {data:{...appointment,starts_at:startsAt},status:201,statusText:'Created',headers:{},config}
    }
    else if(config.url==='/studies/7/appointment') {
      if(!fake.booked) throw failure(config,404,'Not Found','El estudio no tiene un turno vigente.')
      data=appointment
    }
    else if(config.url==='/appointments/55'&&config.method==='delete') {
      if(fake.cancelRejected) throw failure(config,409,'Conflict','No se puede cancelar un turno que ya empezó.')
      fake.booked=false
      return {data:'',status:204,statusText:'No Content',headers:{},config}
    }
    else if(/^\/appointments\/55\/documents\/(order|consent)$/.test(config.url)) {
      // Como axios con responseType blob: el cuerpo del error también es un Blob.
      if(fake.documentRejected) {
        const body=new Blob([JSON.stringify({detail:'Los documentos solo están disponibles para un turno reservado.'})],{type:'application/json'})
        throw new AxiosError('Request failed with status code 409','ERR_BAD_REQUEST',config,null,{status:409,statusText:'Conflict',headers:{},config,data:body})
      }
      data=new Blob(['%PDF-DEMO'],{type:'application/pdf'})
    }
    else if(config.url==='/appointments/mine') data=fake.myAppointments
    else if(config.url==='/studies/999/appointment') throw failure(config,404,'Not Found','El estudio no existe o no es tuyo.')
    // Como el back: un estudio con turno vigente deja de ser elegible.
    else if(config.url==='/appointments/eligible-studies') data=fake.eligible.filter((study)=>!(fake.booked&&study.id===7))
    else if(config.url==='/extraction-centers') data=[...centers,...manyCenters].filter((c)=>c.province_id===Number(config.params.province_id))
    else if(config.url==='/patients') data={items:[],total:0,offset:0,limit:20}
    else if(['/pathologies','/symptoms'].includes(config.url)) data=[]
    else throw new Error(`Petición inesperada ${config.method} ${config.url}`)
    return {data,status:200,statusText:'OK',headers:{},config}
  }
})
afterEach(async () => { await act(async()=>{root.unmount();setSession(null)});dom.happyDOM.abort();dom.close();mock.timers.reset() })

export async function render(path,session=patient) {
  await act(async()=>{setSession(session);root.render(React.createElement(Harness,{initialEntries:[path]}))})
  await settle()
}
// Para renderizar otra ruta en la misma prueba: MemoryRouter no cambia de ruta si se vuelve a renderizar.
export async function remount() { await act(async()=>root.unmount());root=createRoot(container) }
export async function settle() { await act(async()=>{await new Promise((resolve)=>setTimeout(resolve,320))}) }
export async function choose(select,value) {
  await act(async()=>{
    Object.getOwnPropertyDescriptor(dom.HTMLSelectElement.prototype,'value').set.call(select,value)
    select.dispatchEvent(new dom.Event('change',{bubbles:true}))
  })
  await settle()
}
export function button(label) {
  const item=[...container.querySelectorAll('button')].find((b)=>b.textContent.trim()===label)
  assert.ok(item,`No se encontró botón ${label}`);return item
}
export const RESERVE='/paciente/turnos/reservar?estudio=7'
export const province=()=>container.querySelector('#turnos-province')
export const centerButtons=()=>[...container.querySelectorAll('button.turnos-center')]
export const dayButton=(date)=>container.querySelector(`button[data-date="${date}"]`)
export const slotButtons=()=>[...container.querySelectorAll('button.turnos-slot')]
export const lastSlotsDate=()=>calls.filter((c)=>c.url.endsWith('/slots')).at(-1)?.params.date
export const crumb=()=>container.querySelector('.clinical-breadcrumb').textContent
export async function pickCenter(path=RESERVE) {
  await render(path)
  await choose(province(),'1')
  await act(async()=>centerButtons()[0].click())
}
export async function pickDay(date) { await act(async()=>dayButton(date).click());await settle() }
export async function pickSlot(path,label) {
  await pickCenter(path);await pickDay('2026-11-04')
  await act(async()=>slotButtons().find((b)=>b.textContent===label).click())
}
