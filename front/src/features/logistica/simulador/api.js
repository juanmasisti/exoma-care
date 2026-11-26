import { useEffect, useState } from 'react'
import { api } from '../../../services/api.js'

export async function listWaitingStudies() { return (await api.get('/demo/extraction-notice/studies')).data }
export async function simulateNotice(studyCode, volumeMl) {
  return (await api.post('/demo/extraction-notice', { study_code: studyCode, volume_ml: volumeMl })).data
}

// El back es el único interruptor (DEMO_TOOLS_ENABLED): apagado responde 404 y el menú no muestra el simulador.
// Se pregunta una vez por sesión: cada pantalla monta su propio menú.
let probe = { token: null, enabled: null }
export function useSimulatorEnabled(labAdmin, token) {
  const [enabled, setEnabled] = useState(false)
  useEffect(() => {
    if (!labAdmin) return undefined
    if (probe.token !== token) probe = { token, enabled: listWaitingStudies().then(() => true, () => false) }
    let active = true
    probe.enabled.then((value) => { if (active) setEnabled(value) })
    return () => { active = false }
  }, [labAdmin, token])
  return enabled
}
