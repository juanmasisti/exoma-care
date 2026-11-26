import { useEffect, useId, useRef, useState } from 'react'
import { errorMessage } from '../../services/api.js'
import { importTerminology, searchTerminology } from './terminologyApi.js'

export default function SymptomPicker({ label, selected, onChange, multiple = false, excludeIds = [] }) {
  const id = useId()
  const [query, setQuery] = useState('')
  const [options, setOptions] = useState([])
  const [loading, setLoading] = useState(true)
  const [importing, setImporting] = useState(false)
  const [error, setError] = useState('')
  const selectionRequest = useRef(null)
  useEffect(() => () => selectionRequest.current?.abort(), [])

  useEffect(() => {
    const controller = new AbortController()
    const timer = setTimeout(async () => {
      try {
        const result = query.trim().length >= 3 ? await searchTerminology(query.trim(), controller.signal) : []
        if (!controller.signal.aborted) setOptions(result)
      } catch (failure) {
        if (!controller.signal.aborted) setError(errorMessage(failure))
      } finally {
        if (!controller.signal.aborted) setLoading(false)
      }
    }, 250)
    return () => { clearTimeout(timer); controller.abort() }
  }, [query])

  async function choose(event) {
    const term = options.find((item) => String(item.code) === event.target.value)
    if (!term) return
    const controller = new AbortController()
    selectionRequest.current?.abort()
    selectionRequest.current = controller
    setImporting(true); setError('')
    try {
      const imported = await importTerminology(term.selection_token, controller.signal)
      if (!controller.signal.aborted && !excludeIds.includes(imported.id) && !selected.some(item => item.id === imported.id)) {
        onChange(multiple ? [...selected, imported] : [imported])
      }
    } catch (failure) {
      if (!controller.signal.aborted) setError(errorMessage(failure))
    } finally {
      if (!controller.signal.aborted) setImporting(false)
    }
  }

  function resetSearch() { setOptions([]); setLoading(true); setError('') }
  return (
    <fieldset className="term-picker">
      <legend>{label}</legend>
      <p className="catalog-muted">Buscá síntomas en SNOMED CT escribiendo al menos 3 caracteres.</p>
      <label htmlFor={`${id}-query`}>Buscar {label.toLowerCase()}</label>
      <input id={`${id}-query`} type="search" value={query} maxLength={100} disabled={importing}
        placeholder="Buscar por nombre o código" onChange={event => { resetSearch(); setQuery(event.target.value) }} />
      <label htmlFor={`${id}-select`}>Seleccionar {label.toLowerCase()}</label>
      <select id={`${id}-select`} value="" onChange={choose} disabled={loading || importing}>
        <option value="">{importing ? 'Guardando selección...' : loading ? 'Buscando conceptos...' : 'Seleccionar un concepto'}</option>
        {options.filter(term => !excludeIds.includes(term.id) && !selected.some(s => s.id === term.id || (s.code_system === term.code_system && s.code === term.code)))
          .map(term => <option key={term.code_system + term.code} value={term.code}>{term.label} · {term.code_system}: {term.code}</option>)}
      </select>
      {error && <p role="alert" className="catalog-error">{error}</p>}
      {!loading && !error && options.length === 0 && query.trim().length >= 3 && <p className="catalog-muted">No hay conceptos para esta búsqueda.</p>}
      {selected.length > 0 && <ul className="term-list">
        {selected.map(term => <li key={term.id}>
          <span>{term.label}<small>{term.code_system}: {term.code}</small></span>
          <button type="button" className="catalog-text-button" aria-label={`Quitar ${term.label}`} disabled={importing}
            onClick={() => onChange(selected.filter(item => item.id !== term.id))}>Quitar</button>
        </li>)}
      </ul>}
    </fieldset>
  )
}
