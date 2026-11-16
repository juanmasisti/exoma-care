import assert from 'node:assert/strict'
import { after, afterEach, before, beforeEach, test } from 'node:test'
import { Window } from 'happy-dom'
import { createServer } from 'vite'
import React, { act } from 'react'

let server, Harness, PatologiaSelect, api, setSession, root, container, dom, createRoot
let requests, loginRole, studyPayload, historyPayload

before(async () => {
  const bootstrap = new Window()
  globalThis.window = bootstrap
  globalThis.document = bootstrap.document
  createRoot = (await import('react-dom/client')).createRoot
  bootstrap.close()
  server = await createServer({ server: { middlewareMode: true, hmr: false }, appType: 'custom' })
  Harness = (await server.ssrLoadModule('/tests/harness.jsx')).default
  PatologiaSelect = (await server.ssrLoadModule('/src/features/bioinformatica/components/PatologiaSelect.jsx')).default
  api = (await server.ssrLoadModule('/src/services/api.js')).api
  setSession = (await server.ssrLoadModule('/src/services/session.js')).setSession
})

after(async () => { await server?.close() })

beforeEach(() => {
  dom = new Window({ url: 'http://localhost:5173/' })
  globalThis.window = dom
  globalThis.document = dom.document
  globalThis.HTMLElement = dom.HTMLElement
  globalThis.IS_REACT_ACT_ENVIRONMENT = true
  container = document.createElement('div')
  document.body.append(container)
  root = createRoot(container)
  requests = []
  loginRole = 'bioinformatician'
  studyPayload = []
  historyPayload = []
  api.defaults.adapter = async (config) => {
    requests.push({ url: config.url, method: config.method })
    let data
    if (config.url === '/auth/login') {
      data = {
        access_token: 'test-token',
        role: loginRole,
        rol: loginRole === 'super_admin' ? 'Super Admin' : 'Bioinformático',
        user_id: 7,
      }
    } else if (config.url === '/admin/users') {
      data = []
    } else if (config.url === '/bioinformatica/patologias') {
      data = [{ codigo: 'FABRY', nombre: 'Enfermedad de Fabry' }]
    } else if (config.url === '/bioinformatica/estudios') data = studyPayload
    else if (config.url === '/bioinformatica/historial') data = historyPayload
    else if (config.url.endsWith('/reenviar-notificacion') && config.method === 'post') {
      data = { mensaje: 'Aviso de resultado reenviado correctamente.' }
    }
    else if (config.url === '/pathologies' || config.url === '/symptoms') data = []
    else throw new Error(`Petición inesperada: ${config.method} ${config.url}`)
    return { data, status: 200, statusText: 'OK', headers: {}, config }
  }
})

afterEach(async () => {
  await act(async () => { root.unmount(); setSession(null) })
  dom.happyDOM.abort()
  dom.close()
})

async function settle() {
  await act(async () => { await new Promise((resolve) => setTimeout(resolve, 50)) })
}

async function change(input, value) {
  await act(async () => {
    Object.getOwnPropertyDescriptor(dom.HTMLInputElement.prototype, 'value').set.call(input, value)
    input.dispatchEvent(new dom.Event('input', { bubbles: true }))
  })
}

test('el bioinformático llega a su bandeja al iniciar sesión y carga estudios', async () => {
  await act(async () => root.render(React.createElement(Harness, { initialEntries: ['/'] })))
  await change(document.getElementById('identifier'), 'lucas.fernandez@exoma.test')
  await change(document.getElementById('password'), 'demo')
  const loginButton = [...container.querySelectorAll('button')].find((button) => button.textContent.includes('Ingresar'))
  await act(async () => loginButton.click())
  await settle()

  assert.match(container.textContent, /Inicio \/ Dashboard/)
  assert.match(container.textContent, /Bioinformático/)
  assert.ok(requests.some((request) => request.url === '/bioinformatica/estudios'))
  assert.ok(requests.some((request) => request.url === '/bioinformatica/historial'))
  for (const section of ['inicio', 'disponibles', 'analisis', 'historial']) {
    assert.ok(container.querySelector(`a[href="/bioinformatica/dashboard?section=${section}"]`))
  }
})

test('el menú lateral abre el historial consultado al backend', async () => {
  await act(async () => {
    setSession({ access_token: 'test-token', role: 'bioinformatician', user_id: 7 })
    root.render(React.createElement(Harness, {
      initialEntries: ['/bioinformatica/dashboard?section=inicio'],
    }))
  })
  await settle()

  const historyLink = container.querySelector(
    'a[href="/bioinformatica/dashboard?section=historial"]',
  )
  await act(async () => historyLink.click())
  await settle()

  assert.match(container.textContent, /Historial de estudios/)
  assert.ok(requests.some((request) => request.url === '/bioinformatica/historial'))
})

test('las tarjetas muestran exclusivamente datos recibidos del estudio y del paciente', async () => {
  studyPayload = [{
    id: 27,
    patient_id: 18,
    patient_name: 'Paciente almacenado',
    patient_dni: 'DOC-ALMACENADO',
    status: 'en_area_bioinformatica',
    analyst_id: null,
    created_at: '2026-10-12T10:30:00Z',
    codigo_patologia: null,
    patient: {
      id: 18,
      email: 'paciente@example.test',
      clinical_summary: 'Resumen recuperado de la ficha.',
      clinical_revision: {},
      physician: null,
    },
    variantes_detectadas: null,
    resultado_diagnostico: null,
    hallazgos_secundarios: null,
    fecha_reevaluacion: null,
  }]
  await act(async () => {
    setSession({ access_token: 'test-token', role: 'bioinformatician', user_id: 7 })
    root.render(React.createElement(Harness, {
      initialEntries: ['/bioinformatica/dashboard?section=disponibles'],
    }))
  })
  await settle()

  assert.match(container.textContent, /Paciente almacenado/)
  assert.match(container.textContent, /DOC-ALMACENADO/)
  assert.match(container.textContent, /Resumen recuperado de la ficha/)
  assert.equal(container.textContent.includes('Mateo Benítez'), false)
  assert.equal(container.textContent.includes('BRCA1'), false)
})

test('el historial permite reenviar el aviso del resultado al paciente y al médico', async () => {
  historyPayload = [{
    id: 31,
    patient_id: 18,
    patient_name: 'Paciente persistido',
    patient_dni: 'DOC-31',
    status: 'resultado_disponible',
    analyst_id: 7,
    created_at: '2026-10-12T10:30:00Z',
    codigo_patologia: 'PERSISTED-CODE',
    patient: { id: 18, email: 'paciente@example.test' },
    variantes_detectadas: [],
    resultado_diagnostico: 'negativo',
    hallazgos_secundarios: [],
    fecha_reevaluacion: null,
  }]
  await act(async () => {
    setSession({ access_token: 'test-token', role: 'bioinformatician', user_id: 7 })
    root.render(React.createElement(Harness, {
      initialEntries: ['/bioinformatica/dashboard?section=historial'],
    }))
  })
  await settle()

  const resendButton = [...container.querySelectorAll('button')]
    .find((button) => button.textContent.includes('Reenviar aviso'))
  assert.ok(resendButton)
  await act(async () => resendButton.click())
  await settle()

  assert.ok(requests.some((request) => (
    request.method === 'post'
    && request.url === '/bioinformatica/estudios/31/reenviar-notificacion'
  )))
  assert.match(container.textContent, /Se reenvió el aviso de resultado disponible/)
})

test('un superadministrador no puede abrir la bandeja bioinformática', async () => {
  await act(async () => {
    setSession({ access_token: 'test-token', role: 'super_admin', rol: 'Super administrador' })
    root.render(React.createElement(Harness, { initialEntries: ['/bioinformatica/dashboard'] }))
  })
  await settle()

  assert.match(container.textContent, /Administración de usuarios/)
  assert.equal(container.textContent.includes('Bandeja de análisis'), false)
  assert.equal(requests.some((request) => request.url === '/bioinformatica/estudios'), false)
})

test('el Super Admin llega al dashboard de usuarios al iniciar sesión', async () => {
  loginRole = 'super_admin'
  await act(async () => root.render(React.createElement(Harness, { initialEntries: ['/'] })))
  await change(document.getElementById('identifier'), 'superadmin@example.test')
  await change(document.getElementById('password'), 'demo')
  const loginButton = [...container.querySelectorAll('button')].find((button) => button.textContent.includes('Ingresar'))
  await act(async () => loginButton.click())
  await settle()

  assert.match(container.textContent, /Administración de usuarios/)
  assert.ok(requests.some((request) => request.url === '/admin/users'))
})

test('el selector carga el catálogo CDSS y mantiene código como valor controlado', async () => {
  await act(async () => root.render(React.createElement(PatologiaSelect, {
    value: 'FABRY',
    onChange: () => {},
  })))
  await settle()

  const select = container.querySelector('select')
  assert.ok(select)
  assert.equal(select.value, 'FABRY')
  assert.equal(select.querySelector('option[value="FABRY"]').textContent, 'Enfermedad de Fabry (FABRY)')
  assert.ok(requests.some((request) => request.url === '/bioinformatica/patologias'))
})
