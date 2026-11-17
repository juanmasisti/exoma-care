import { useEffect, useRef, useState } from 'react'
import { errorMessage } from '../../services/api.js'
import { getGeneticCatalog, getCDSSCatalog, getGenes, createGeneticPathology, linkPathology, importCDSSDraft } from './clinicalIntegrationsApi.js'

export default function ExternalPathologyPanel({ pathology, onLinked, onCriteriaDraft, disabled = false }) {
  const mounted = useRef(true)
  useEffect(() => { mounted.current = true; return () => { mounted.current = false } }, [])
  const [genetic, setGenetic] = useState([])
  const [clinical, setClinical] = useState([])
  const [selected, setSelected] = useState('')
  const [cdssCode, setCdssCode] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [draft, setDraft] = useState({ codigo: '', nombre: '', genes: [], herencia: 'autosomica_recesiva' })
  const [geneQuery, setGeneQuery] = useState('')
  const [genes, setGenes] = useState([])
  const [criteria, setCriteria] = useState(null)
  const [cardinal, setCardinal] = useState('')
  const [confirmed, setConfirmed] = useState(false)
  const chosen = genetic.find((p) => `${p.de_grupo}:${p.codigo}` === selected)
  async function action(fn) {
    if (disabled) return
    setBusy(true); setError(''); setNotice('')
    try { await fn() } catch (failure) { setError(errorMessage(failure)) } finally { setBusy(false) }
  }
  async function load() {
    const results = await Promise.allSettled([getGeneticCatalog(), getCDSSCatalog()])
    if (results[0].status === 'fulfilled') setGenetic(results[0].value)
    if (results[1].status === 'fulfilled') setClinical(results[1].value)
    const failed = results.find((r) => r.status === 'rejected')
    if (failed) throw failed.reason
  }
  return <section className="catalog-card catalog-external" aria-label="Identidad genética externa">
    <fieldset disabled={disabled} className="catalog-fieldset"><h2>Identidad genética externa</h2>
    <p>Asociá códigos externos a los criterios clínicos guardados. La asociación conserva el nombre, los síntomas y las revisiones históricas locales.</p>
    <button type="button" className="catalog-secondary" disabled={disabled || busy} onClick={() => action(load)}>Consultar catálogos externos</button>
    {error && <p role="alert" className="catalog-error">{error}</p>}
    {notice && <p role="status" className="catalog-success">{notice}</p>}
    {pathology?.apigen_code ? <p>Identidad asociada: <strong>{pathology.apigen_code}</strong> ({pathology.apigen_group || 'catálogo base'}). CDSS: {pathology.cdss_code || 'sin correspondencia configurada'}. La identidad es estable.</p> : <>
      <p>{pathology ? `Asociar a: ${pathology.name}` : 'Guardá o seleccioná una patología local antes de asociar la identidad.'}</p>
      <label>Patología Apigen<select aria-label="Patología Apigen" value={selected} disabled={disabled || busy} onChange={(e) => setSelected(e.target.value)}><option value="">Seleccioná una identidad</option>{genetic.map((p) => <option key={`${p.de_grupo}:${p.codigo}`} value={`${p.de_grupo}:${p.codigo}`}>{p.codigo} · {p.nombre} {p.de_grupo ? '(grupo)' : ''}</option>)}</select></label>
      {chosen && <p>Genes: {chosen.genes.join(', ')}. Herencia: {chosen.herencia}.</p>}
      <label>Correspondencia CDSS<select aria-label="Correspondencia CDSS" value={cdssCode} disabled={disabled || busy} onChange={(e) => setCdssCode(e.target.value)}><option value="">Sin correspondencia CDSS</option>{clinical.map((p) => <option key={p.codigo} value={p.codigo}>{p.codigo} · {p.nombre}</option>)}</select></label>
      <p>Verificá ambos códigos. Una patología genética puede no estar cubierta por CDSS.</p>
      <button type="button" className="catalog-primary" disabled={disabled || busy || !pathology || !chosen} onClick={() => action(async () => { const saved = await linkPathology(pathology.id, { apigen_code: chosen.codigo, de_grupo: chosen.de_grupo, cdss_code: cdssCode || null }); if (!mounted.current) return; onLinked(saved); setNotice('Identidad externa asociada. Se conservaron los criterios clínicos.'); })}>Asociar identidad externa</button>
    </>}
    {clinical.length > 0 && <details><summary>Consultar criterios externos CDSS</summary><p>Referencia externa; no modifica las reglas locales.</p>{clinical.map((p) => <details key={p.codigo}><summary>{p.codigo} · {p.nombre}</summary><button type="button" disabled={disabled || busy} onClick={() => action(async () => { setCriteria(await importCDSSDraft(p.codigo)); setCardinal(''); })}>Preparar criterios de {p.codigo}</button><ul>{p.sintomas.map((s) => <li key={s.snomed_codigo}>{s.termino} · {s.snomed_codigo} {s.es_cardinal ? '(cardinal)' : '(secundario)'}</li>)}</ul></details>)}</details>}
    {criteria && <div><h3>Preparar criterios de {criteria.codigo}</h3><p>Elegí un único cardinal. Los demás cardinales externos no se convierten automáticamente en secundarios. Esto reemplaza el borrador; revisalo y guardá para aplicar cambios.</p>
      <label>Cardinal del borrador<select aria-label="Cardinal del borrador" value={cardinal} onChange={(e) => setCardinal(e.target.value)}><option value="">Seleccioná un cardinal</option>{criteria.cardinals.map((s) => <option key={s.id} value={s.id}>{s.label}</option>)}</select></label>
      <button type="button" disabled={disabled || !cardinal || busy} onClick={() => { onCriteriaDraft(criteria.cardinals.find((s) => String(s.id) === cardinal), criteria.secondary); setNotice('Criterios preparados en el borrador. Revisá y guardá la patología local.'); setCriteria(null); }}>Usar criterios en el borrador local</button>
    </div>}
    <details><summary>Crear patología genética del grupo en Apigen</summary>
      <p>Esta acción escribe en Apigen. Después deberás asociar el código a una definición clínica local. Si la respuesta falla, actualizá el catálogo antes de repetir el alta.</p>
      <label>Código nuevo<input aria-label="Código genético nuevo" maxLength={100} pattern="[A-Z0-9_-]+" value={draft.codigo} onChange={(e) => setDraft({ ...draft, codigo: e.target.value.toUpperCase() })} /></label>
      <label>Nombre genético<input aria-label="Nombre genético" maxLength={160} value={draft.nombre} onChange={(e) => setDraft({ ...draft, nombre: e.target.value })} /></label>
      <label>Herencia<select aria-label="Herencia" value={draft.herencia} onChange={(e) => setDraft({ ...draft, herencia: e.target.value })}><option value="autosomica_recesiva">Autosómica recesiva</option><option value="autosomica_dominante">Autosómica dominante</option><option value="ligada_al_x">Ligada al X</option></select></label>
      <label>Buscar gen<input aria-label="Buscar gen" value={geneQuery} onChange={(e) => setGeneQuery(e.target.value)} /></label><button type="button" disabled={disabled || busy || geneQuery.trim().length < 2} onClick={() => action(async () => setGenes(await getGenes(geneQuery.trim())))}>Buscar genes en Apigen</button>
      <ul>{genes.filter((g) => !draft.genes.includes(g)).map((g) => <li key={g}><button type="button" onClick={() => setDraft({ ...draft, genes: [...draft.genes, g] })}>Agregar {g}</button></li>)}</ul>
      <ul>{draft.genes.map((g) => <li key={g}>{g} <button type="button" onClick={() => setDraft({ ...draft, genes: draft.genes.filter((v) => v !== g) })}>Quitar {g}</button></li>)}</ul>
      <label><input type="checkbox" checked={confirmed} onChange={(e) => setConfirmed(e.target.checked)} />Confirmo crear esta patología en Apigen para el grupo configurado.</label>
      <button type="button" className="catalog-primary" disabled={disabled || busy || !confirmed || !draft.codigo || !draft.nombre.trim() || !draft.genes.length} onClick={() => action(async () => { const saved = await createGeneticPathology({ ...draft, confirm_remote_write: true }); setGenetic((items) => [...items.filter((p) => p.codigo !== saved.pathology.codigo), saved.pathology]); setSelected(`true:${saved.pathology.codigo}`); setConfirmed(false); setNotice(saved.message); })}>Crear en Apigen</button>
    </details>
  </fieldset></section>
}
