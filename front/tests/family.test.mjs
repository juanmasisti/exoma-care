import assert from 'node:assert/strict'
import { after, afterEach, before, beforeEach, test } from 'node:test'
import { Window } from 'happy-dom'
import { createServer } from 'vite'
import React, { act } from 'react'
import { AxiosError } from 'axios'

let server, Harness, api, setSession, createRoot, root, container, dom
let requests, family, conflict
const physician={access_token:'test-token',role:'treating_physician',rol:'Médico'}
const terms=[{id:1,code:'DEMO-1',label:'Síntoma de prueba',code_system:'DEMO'}]
const pathologies=[{id:1,name:'Enfermedad de Fabry',cardinal_symptom:terms[0],secondary_symptoms:[]}]
const patient={id:1,dni:'45000111',first_name:'Ana',last_name:'Prueba',birth_date:'1990-01-01',phone:'000',email:'ana@example.test',clinical_summary:'Resumen ficticio',suspicion_type:'clinical',family_history:'',pathology_ids:[1],symptom_ids:[1],symptoms:terms,suspicions:[],version:1,access_status:'pending'}

before(async()=>{
  const bootstrap=new Window();globalThis.window=bootstrap;globalThis.document=bootstrap.document
  createRoot=(await import('react-dom/client')).createRoot;bootstrap.close()
  server=await createServer({server:{middlewareMode:true,hmr:false},appType:'custom'})
  Harness=(await server.ssrLoadModule('/tests/harness.jsx')).default
  api=(await server.ssrLoadModule('/src/services/api.js')).api
  setSession=(await server.ssrLoadModule('/src/services/session.js')).setSession
})
after(async()=>{await server?.close()})
beforeEach(()=>{
  dom=new Window({url:'http://localhost:5173/'});globalThis.window=dom;globalThis.document=dom.document;globalThis.HTMLElement=dom.HTMLElement;globalThis.IS_REACT_ACT_ENVIRONMENT=true
  container=document.createElement('div');document.body.append(container);root=createRoot(container)
  requests=[];conflict=false;family={patient_id:1,version:0,members:[],updated_at:null,familiogram_status:'not_configured'}
  api.defaults.adapter=async(config)=>{
    const body=typeof config.data==='string'?JSON.parse(config.data):config.data
    requests.push({url:config.url,method:config.method,body})
    let data
    if(config.url==='/patients/1')data=patient
    else if(config.url==='/patients/1/history')data=[]
    else if(config.url==='/pathologies')data=pathologies
    else if(config.url==='/symptoms')data=terms
    else if(config.url==='/patients/1/family/history')data=family.version?[{version:family.version,changed_at:'2026-10-31T12:00:00',changed_by_name:'Médico Prueba',members:family.members}]:[]
    else if(config.url==='/patients/1/family'&&config.method==='get')data=family
    else if(config.url==='/patients/1/family'&&config.method==='put'){
      if(conflict)throw new AxiosError('Conflict','ERR_BAD_REQUEST',config,null,{status:409,data:{detail:'Otro médico modificó la información familiar. Recargá antes de guardar.'}})
      family={...family,version:family.version+1,members:body.members.map(m=>({...m,symptoms:terms.filter(t=>m.symptom_ids.includes(t.id)),diagnoses:pathologies.filter(p=>m.diagnosis_ids.includes(p.id)).map(p=>({id:p.id,name:p.name}))}))};data=family
    }else throw new Error(`Petición inesperada ${config.method} ${config.url}`)
    return{data,status:200,statusText:'OK',headers:{},config}
  }
})
afterEach(async()=>{await act(async()=>{root.unmount();setSession(null)});dom.happyDOM.abort();dom.close()})
async function settle(){await act(async()=>{await new Promise(resolve=>setTimeout(resolve,320))})}
async function click(label){const button=[...container.querySelectorAll('button')].find(b=>b.textContent.trim()===label);assert.ok(button,`Falta el botón ${label}`);await act(async()=>button.click());await settle()}
function control(label){const l=[...container.querySelectorAll('label')].find(l=>l.textContent.trim().replace(/ \*$/,'')===label);assert.ok(l,`Falta el campo ${label}`);return l.htmlFor?document.getElementById(l.htmlFor):l.querySelector('input')}
async function change(el,value){await act(async()=>{const proto=el.tagName==='SELECT'?dom.HTMLSelectElement.prototype:el.tagName==='TEXTAREA'?dom.HTMLTextAreaElement.prototype:dom.HTMLInputElement.prototype;Object.getOwnPropertyDescriptor(proto,'value').set.call(el,value);el.dispatchEvent(new dom.Event(el.tagName==='SELECT'?'change':'input',{bubbles:true}))})}
async function render(){await act(async()=>{setSession(physician);root.render(React.createElement(Harness,{initialEntries:['/medico/pacientes/1']}))});await settle()}
async function openFamily(){await render();await click('Familiares')}
async function addMember(){await click('Editar familiares');await click('Agregar familiar');await change(control('Nombre del familiar'),'María Prueba');await change(control('Parentesco'),'mother');await click('Incorporar a la lista')}

test('familia opcional vacía se consulta solo al abrir su pestaña y PDF queda pendiente',async()=>{
  await render();assert.equal(requests.some(r=>r.url.includes('/family')),false)
  await click('Familiares')
  assert.match(container.textContent,/Todavía no hay familiares registrados/)
  assert.match(container.textContent,/PDF.*pendiente|pendiente.*PDF/i)
  assert.equal(container.querySelector('a[download]'),null)
})

test('agregar familiar no crea pacientes ni guarda hasta confirmar la lista',async()=>{
  await openFamily();await addMember()
  assert.equal(requests.some(r=>r.method==='put'),false)
  await click('Guardar información familiar')
  const request=requests.find(r=>r.method==='put')
  assert.equal(request.body.version,0)
  assert.equal(request.body.members[0].full_name,'María Prueba')
  assert.deepEqual(request.body.members[0].symptom_ids,[])
  assert.equal(request.body.members[0].diagnosis_status,'unknown')
  assert.match(container.textContent,/Información familiar guardada/)
  assert.equal(requests.some(r=>r.method==='post'),false)
})

test('diagnóstico conocido exige seleccionar una patología sin inferirla de síntomas',async()=>{
  await openFamily();await click('Editar familiares');await click('Agregar familiar')
  await change(control('Nombre del familiar'),'Familiar ficticio');await change(control('Parentesco'),'father')
  await change(control('Información diagnóstica'),'known');await click('Incorporar a la lista')
  assert.match(container.textContent,/Seleccioná al menos una patología/)
  await act(async()=>control('Enfermedad de Fabry').click());await click('Incorporar a la lista');await click('Guardar información familiar')
  const saved=requests.find(r=>r.method==='put').body.members[0]
  assert.deepEqual(saved.diagnosis_ids,[1]);assert.deepEqual(saved.symptom_ids,[])
})

test('conflicto al guardar conserva la lista y el nombre editado',async()=>{
  await openFamily();await addMember();conflict=true;await click('Guardar información familiar')
  assert.match(container.textContent,/Otro médico modificó/)
  assert.match(container.textContent,/María Prueba/)
  assert.ok([...container.querySelectorAll('button')].some(b=>b.textContent==='Guardar información familiar'))
})

test('quitar requiere confirmar guardado y conserva el historial',async()=>{
  family={...family,version:1,members:[{full_name:'María Prueba',relationship:'mother',relationship_detail:'',symptom_ids:[],diagnosis_status:'none',diagnosis_ids:[],notes:'',symptoms:[],diagnoses:[]}]}
  await openFamily();await click('Editar familiares');await click('Quitar María Prueba')
  assert.equal(requests.some(r=>r.method==='put'),false)
  await click('Cancelar edición');assert.match(container.textContent,/María Prueba/)
  await click('Ver historial familiar');assert.match(container.textContent,/Médico Prueba/)
})

test('borradores se conservan al navegar entre pestañas de la ficha',async()=>{
  await openFamily();await addMember();await click('Información clínica');await click('Familiares')
  assert.match(container.textContent,/María Prueba/)
  assert.equal(requests.some(r=>r.method==='put'),false)
})


test('después de comparar se puede conservar el borrador y guardar sobre versión actual explícitamente',async()=>{
  await openFamily();await addMember()
  family={...family,version:2,members:[]};conflict=true
  await click('Guardar información familiar');await click('Consultar versión actual')
  assert.match(container.textContent,/Versión guardada 2/)
  await click('Continuar con mi borrador sobre la versión actual')
  assert.match(container.textContent,/María Prueba/)
  conflict=false;await click('Guardar información familiar')
  const updates=requests.filter(r=>r.method==='put')
  assert.equal(updates.length,2)
  assert.equal(updates[1].body.version,2)
  assert.equal(updates[1].body.members[0].full_name,'María Prueba')
})
