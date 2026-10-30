import assert from 'node:assert/strict'
import { after, afterEach, before, beforeEach, test } from 'node:test'
import { Window } from 'happy-dom'
import { createServer } from 'vite'
import React, { act } from 'react'
import { AxiosError } from 'axios'

let server, Harness, api, setSession, createRoot, root, container, dom
let calls, records, rejectSave, conflict
const doctor = { access_token: 'test-token', role: 'treating_physician', rol: 'Médico' }
const terms = [1,2,3,4].map((id) => ({ id, code: `DEMO-${id}`, label: `Síntoma demo ${id}`, code_system: 'DEMO' }))
const catalog = [{ id:1,name:'Enfermedad de Fabry',cardinal_symptom:terms[0],secondary_symptoms:[terms[1],terms[2]] },
  { id:2,name:'Enfermedad de Pompe',cardinal_symptom:terms[3],secondary_symptoms:[] }]
const patient = () => ({ id:1,dni:'45000111',first_name:'Ana',last_name:'Prueba',birth_date:'1990-01-01',phone:'000',email:'ana@example.test',clinical_summary:'Resumen ficticio original',suspicion_type:'clinical',family_history:'',pathology_ids:[1],symptom_ids:[1],symptoms:[terms[0]],suspicions:[{pathology_id:1,name:'Enfermedad de Fabry',valid:true,criterion:'cardinal',definition:catalog[0]}],version:1,access_status:'pending',created_by_physician_id:1,clinical_record_complete:true })

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
  calls=[];records=[];rejectSave=false;conflict=false
  api.defaults.adapter=async (config) => {
    const body=typeof config.data==='string'?JSON.parse(config.data):config.data
    calls.push({url:config.url,method:config.method,body,params:config.params})
    let data
    if(config.url==='/auth/login') data=doctor
    else if(config.url==='/pathologies') data=catalog
    else if(config.url==='/symptoms') data=terms
    else if(config.url.endsWith('/history')) data=[{version:1,changed_by_name:'Médico Demo',changed_at:'2026-10-29T12:00:00',snapshot:{patient_data:{clinical_summary:'Resumen ficticio original'},suspicions:patient().suspicions}}]
    else if(config.url==='/patients' && config.method==='get') {
      const q=config.params.q.toLowerCase()
      const visible=records.filter((r)=>`${r.first_name} ${r.last_name} ${r.dni}`.toLowerCase().includes(q))
      data={items:visible.map((r)=>({...r,pathology_names:r.suspicions.map((s)=>s.name)})),total:visible.length,offset:0,limit:20}
    } else if(config.url==='/patients/validate') data={valid:true,results:patient().suspicions}
    else if(config.url.startsWith('/patients/') && config.method==='get') data=records.find((r)=>r.id===Number(config.url.split('/')[2]))??patient()
    else if(config.url.startsWith('/patients') && ['post','put'].includes(config.method)) {
      if(rejectSave) throw new AxiosError('validation','ERR_BAD_REQUEST',config,null,{status:422,data:{detail:{message:'Todas las sospechas clínicas deben cumplir los criterios.',results:[patient().suspicions[0],{pathology_id:2,name:'Enfermedad de Pompe',valid:false,criterion:'insufficient_symptoms'}]}}})
      if(conflict) throw new AxiosError('version','ERR_BAD_REQUEST',config,null,{status:409,data:{detail:'Otra edición modificó el paciente. Recargá su ficha antes de guardar.'}})
      const results=body.pathology_ids.map((id)=>({pathology_id:id,name:catalog.find((p)=>p.id===id).name,valid:true,criterion:body.suspicion_type==='family'?'family_history':'cardinal'}))
      data={...patient(),...body,id:1,version:config.method==='put'?2:1,symptoms:terms.filter((t)=>body.symptom_ids.includes(t.id)),suspicions:results}
      records=[data]
    } else throw new Error(`Petición inesperada ${config.method} ${config.url}`)
    return {data,status:200,statusText:'OK',headers:{},config}
  }
})
afterEach(async () => { await act(async()=>{root.unmount();setSession(null)});dom.happyDOM.abort();dom.close() })

async function render(path,session=doctor) {
  await act(async()=>{setSession(session);root.render(React.createElement(Harness,{initialEntries:[path]}))})
  await settle()
}
async function settle() { await act(async()=>{await new Promise((resolve)=>setTimeout(resolve,320))}) }
function control(label) {
  const item=[...container.querySelectorAll('label')].find((l)=>l.textContent.trim().replace(/ \*$/,'')===label)
  assert.ok(item,`No se encontró ${label}`)
  return item.htmlFor?document.getElementById(item.htmlFor):item.querySelector('input')
}
function button(label) {
  const item=[...container.querySelectorAll('button')].find((b)=>b.textContent.trim()===label)
  assert.ok(item,`No se encontró botón ${label}`);return item
}
async function click(item) { await act(async()=>item.click()) }
async function change(item,value) {
  await act(async()=>{
    const proto=item.tagName==='SELECT'?dom.HTMLSelectElement.prototype:item.tagName==='TEXTAREA'?dom.HTMLTextAreaElement.prototype:dom.HTMLInputElement.prototype
    Object.getOwnPropertyDescriptor(proto,'value').set.call(item,value)
    item.dispatchEvent(new dom.Event(item.tagName==='SELECT'?'change':'input',{bubbles:true}))
  })
}
async function fillPersonal() {
  for(const [label,value] of [['DNI','45000111'],['Nombre','Ana'],['Apellido','Prueba'],['Fecha de nacimiento','1990-01-01'],['Teléfono','000'],['Email de contacto','ana@example.test'],['Resumen de historia clínica','Resumen ficticio']]) await change(control(label),value)
}

test('el login del médico abre pacientes y conserva la navegación al catálogo',async()=>{
  await render('/',null)
  await change(document.getElementById('identifier'),'medico@example.test')
  await change(document.getElementById('password'),'demo-test')
  await click(button('Ingresar al portal'));await settle()
  assert.equal(container.querySelector('h1').textContent,'Pacientes')
  assert.ok(container.querySelector('a[href="/catalogo/patologias"]'))
  assert.ok(calls.some((c)=>c.url==='/patients'))
})

test('el listado consulta el backend y busca por nombre',async()=>{
  records=[patient()]
  await render('/medico/pacientes')
  assert.match(container.textContent,/Prueba, Ana/)
  await change(control('Buscar pacientes'),'Ausente');await settle()
  assert.match(container.textContent,/No se encontraron pacientes/)
  assert.equal(calls.filter((c)=>c.url==='/patients').at(-1).params.q,'Ausente')
})

test('el alta clínica guarda paciente y no llama a estudios ni crea credenciales',async()=>{
  await render('/medico/pacientes/nuevo');await fillPersonal()
  await click(control('Enfermedad de Fabry'))
  await change(control('Seleccionar síntomas presentes'),'1')
  await click(button('Guardar paciente'));await settle()
  const request=calls.find((c)=>c.url==='/patients'&&c.method==='post')
  assert.deepEqual(request.body.pathology_ids,[1])
  assert.deepEqual(request.body.symptom_ids,[1])
  assert.equal(request.body.suspicion_type,'clinical')
  assert.match(container.textContent,/Paciente registrado/)
  assert.match(container.textContent,/Pendiente de habilitación/)
  assert.equal(calls.some((c)=>/studies|users/.test(c.url)),false)
})

test('la sospecha familiar permite guardar sin síntomas con antecedente',async()=>{
  await render('/medico/pacientes/nuevo');await fillPersonal()
  await change(control('Tipo de sospecha'),'family')
  await change(control('Antecedente familiar documentado'),'Antecedente ficticio documentado')
  await click(control('Enfermedad de Fabry'))
  await click(button('Guardar paciente'));await settle()
  const request=calls.find((c)=>c.url==='/patients'&&c.method==='post')
  assert.equal(request.body.suspicion_type,'family')
  assert.deepEqual(request.body.symptom_ids,[])
  assert.equal(request.body.family_history,'Antecedente ficticio documentado')
  assert.match(container.textContent,/Sospecha familiar/)
})

test('un rechazo mixto muestra el criterio por patología y conserva el formulario',async()=>{
  rejectSave=true
  await render('/medico/pacientes/nuevo');await fillPersonal()
  await click(control('Enfermedad de Fabry'));await click(control('Enfermedad de Pompe'))
  await change(control('Seleccionar síntomas presentes'),'1')
  await click(button('Guardar paciente'))
  assert.match(container.querySelector('[role="alert"]').textContent,/Todas las sospechas/)
  assert.match(container.querySelector('[aria-label="Resultados por sospecha"]').textContent,/Enfermedad de Pompe/)
  assert.equal(control('Nombre').value,'Ana')
  assert.equal(records.length,0)
})

test('la edición envía versión y un conflicto conserva el texto nuevo',async()=>{
  records=[patient()];conflict=true
  await render('/medico/pacientes/1/editar')
  await change(control('Resumen de historia clínica'),'Resumen nuevo sin sobrescribir')
  await click(button('Guardar cambios'))
  const request=calls.find((c)=>c.method==='put')
  assert.equal(request.body.version,1)
  assert.match(container.querySelector('[role="alert"]').textContent,/Otra edición/)
  assert.equal(control('Resumen de historia clínica').value,'Resumen nuevo sin sobrescribir')
})

test('la ficha presenta el historial guardado sin reinterpretar la evidencia',async()=>{
  records=[patient()]
  await render('/medico/pacientes/1')
  await click(button('Historial de cambios (1)'))
  assert.match(container.querySelector('[role="tabpanel"]').textContent,/Resumen ficticio original/)
  assert.match(container.querySelector('[role="tabpanel"]').textContent,/Médico Demo/)
})

test('el gerente no puede entrar a pacientes ni dispara peticiones de pacientes',async()=>{
  await render('/medico/pacientes',{...doctor,role:'medical_manager',rol:'Gerente'})
  assert.equal(container.querySelector('h1').textContent,'Catálogo de patologías')
  assert.equal(calls.some((c)=>c.url.startsWith('/patients')),false)
})
