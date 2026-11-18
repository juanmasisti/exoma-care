import assert from 'node:assert/strict'
import { after, afterEach, before, beforeEach, test } from 'node:test'
import { Window } from 'happy-dom'
import { createServer } from 'vite'
import React, { act, StrictMode } from 'react'

let server, Harness, PatologiaSelect, api, setSession, restoreSession, getSession, root, container, dom, createRoot
let requests, loginRole, studyPayload, historyPayload, pathologyPayload

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
  const sessionModule = await server.ssrLoadModule('/src/services/session.js')
  setSession = sessionModule.setSession
  restoreSession = sessionModule.restoreSession
  getSession = sessionModule.getSession
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
  pathologyPayload = [{ codigo: 'FABRY', nombre: 'Enfermedad de Fabry' }]
  api.defaults.adapter = async (config) => {
    requests.push({ url: config.url, method: config.method, params: config.params })
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
      data = pathologyPayload
    } else if (config.url === '/bioinformatica/estudios') data = studyPayload
    else if (config.url.endsWith('/iniciar') && config.method === 'patch') {
      data = { ...studyPayload[0], status: 'en_analisis', analyst_id: 7, genes: [] }
    } else if (config.url.endsWith('/variantes') && config.method === 'get') {
      data = {
        items: [{ id: 4, hgvs_c: 'c.1A>G', proteina: 'p.1', clasificacion: 'patogenica' }],
        total: 1,
        limit: 50,
        offset: 0,
      }
    }
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

test('la sesión guardada se restaura al recargar la aplicación', async () => {
  const savedSession = {
    access_token: 'restored-token',
    role: 'bioinformatician',
    user_id: 7,
  }
  setSession(savedSession)
  assert.deepEqual(
    JSON.parse(window.sessionStorage.getItem('exoma-care-session')),
    savedSession,
  )
  setSession(null)
  assert.equal(window.sessionStorage.getItem('exoma-care-session'), null)

  window.sessionStorage.setItem('exoma-care-session', JSON.stringify(savedSession))

  assert.deepEqual(restoreSession(), savedSession)
  assert.deepEqual(getSession(), savedSession)
  await act(async () => root.render(React.createElement(Harness, {
    initialEntries: ['/bioinformatica/dashboard?section=inicio'],
  })))
  await settle()

  assert.match(container.textContent, /Inicio \/ Dashboard/)
  assert.ok(requests.some((request) => request.url === '/bioinformatica/estudios'))
})

test('el modo estricto no duplica las consultas iniciales del dashboard', async () => {
  await act(async () => {
    setSession({ access_token: 'test-token', role: 'bioinformatician', user_id: 7 })
    root.render(React.createElement(StrictMode, null, React.createElement(Harness, {
      initialEntries: ['/bioinformatica/dashboard?section=inicio'],
    })))
  })
  await settle()

  assert.equal(
    requests.filter((request) => request.url === '/bioinformatica/estudios').length,
    1,
  )
  assert.equal(
    requests.filter((request) => request.url === '/bioinformatica/historial').length,
    1,
  )
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

test('el análisis consulta Apigen con los genes solicitados por el médico', async () => {
  studyPayload = [{
    id: 27,
    patient_id: 18,
    patient_name: 'Paciente almacenado',
    patient_dni: 'DOC-ALMACENADO',
    status: 'en_area_bioinformatica',
    analyst_id: null,
    created_at: '2026-10-12T10:30:00Z',
    genes: [{ symbol: 'GAA', origin: 'catalogo' }, { symbol: 'GBA', origin: 'manual' }],
    patient: { id: 18, clinical_revision: {}, physician: null },
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

  const takeStudy = [...container.querySelectorAll('button')]
    .find((button) => button.textContent.includes('Tomar estudio'))
  await act(async () => takeStudy.click())
  await settle()

  const geneSelect = document.getElementById('bioinformatics-gene')
  assert.deepEqual([...geneSelect.options].map((option) => option.value), ['', 'GAA', 'GBA'])
  assert.equal(geneSelect.value, 'GAA')
  const search = [...container.querySelectorAll('button')]
    .find((button) => button.textContent.includes('Buscar variantes'))
  await act(async () => search.click())
  await settle()

  assert.ok(requests.some((request) => (
    request.method === 'get'
    && request.url === '/bioinformatica/estudios/27/variantes'
    && request.params.gen === 'GAA'
  )))
  assert.match(container.textContent, /GAA: c\.1A>G/)
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

  const input = container.querySelector('#bioinformatics-pathology')
  assert.equal(input.type, 'text')
  assert.equal(input.value, 'Enfermedad de Fabry (FABRY)')
  assert.equal(container.querySelectorAll('input').length, 1)
  assert.equal(container.querySelector('select'), null)
  assert.ok(requests.some((request) => request.url === '/bioinformatica/patologias'))
})

test('el selector pagina el catálogo y lo carga una sola vez en StrictMode', async () => {
  pathologyPayload = Array.from({ length: 53 }, (_, index) => ({
    codigo: `P${String(index + 1).padStart(3, '0')}`,
    nombre: `Patología ${index + 1}`,
  }))

  await act(async () => root.render(React.createElement(StrictMode, null, React.createElement(PatologiaSelect, {
    value: '',
    onChange: () => {},
  }))))
  await settle()

  const input = container.querySelector('#bioinformatics-pathology')
  await act(async () => input.focus())
  assert.equal(container.querySelectorAll('input').length, 1)
  assert.equal(container.querySelectorAll('[role="option"]').length, 25)
  assert.match(container.textContent, /Mostrando 1-25 de 53/)
  assert.equal(
    requests.filter((request) => request.url === '/bioinformatica/patologias').length,
    1,
  )

  const nextPage = [...container.querySelectorAll('button')]
    .find((button) => button.textContent === 'Siguiente')
  await act(async () => nextPage.click())
  assert.equal(container.querySelectorAll('[role="option"]').length, 25)
  assert.match(container.textContent, /Patología 26 \(P026\)/)
  assert.match(container.textContent, /Mostrando 26-50 de 53/)

  let selectedCode = null
  await act(async () => root.render(React.createElement(PatologiaSelect, {
    value: '',
    onChange: (event) => { selectedCode = event.target.value },
  })))
  await settle()
  await act(async () => container.querySelector('#bioinformatics-pathology').focus())
  await change(container.querySelector('#bioinformatics-pathology'), 'P053')
  assert.equal(container.querySelectorAll('[role="option"]').length, 1)
  assert.match(container.textContent, /Patología 53 \(P053\)/)
  assert.match(container.textContent, /Mostrando 1-1 de 1/)
  const result = [...container.querySelectorAll('[role="option"] button')]
    .find((button) => button.textContent.includes('P053'))
  await act(async () => result.click())
  assert.equal(selectedCode, 'P053')
  assert.equal(container.querySelector('[role="listbox"]'), null)
  assert.equal(container.textContent.includes('No se encontraron patologías.'), false)
  assert.equal(
    container.querySelector('#bioinformatics-pathology').value,
    'Patología 53 (P053)',
  )
})
