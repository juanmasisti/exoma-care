import { useEffect, useId, useState } from 'react'
import { errorMessage } from '../../services/api.js'
import { searchSymptoms } from './api.js'

export default function SymptomPicker({ label, selected, onChange, multiple = false, excludeIds = [] }) {
  const id = useId()
  const [query, setQuery] = useState('')
  const [options, setOptions] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    const controller = new AbortController()
    const timer = setTimeout(async () => {
      try {
        const result = await searchSymptoms(query, controller.signal)
        if (!controller.signal.aborted) setOptions(result)
      } catch (failure) {
        if (!controller.signal.aborted) setError(errorMessage(failure))
      } finally {
        if (!controller.signal.aborted) setLoading(false)
      }
    }, 250)
    return () => { clearTimeout(timer); controller.abort() }
  }, [query])

  function choose(event) {
    const term = options.find((item) => item.id === Number(event.target.value))
    if (!term) return
    onChange(multiple ? [...selected, term] : [term])
  }

  return (
    <fieldset className="term-picker">
      <legend>{label}</legend>
      <label htmlFor={`${id}-query`}>Buscar {label.toLowerCase()}</label>
      <input id={`${id}-query`} type="search" value={query} maxLength={100}
        placeholder="Buscar por nombre o código" onChange={(event) => { setLoading(true); setError(''); setQuery(event.target.value) }} />
      <label htmlFor={`${id}-select`}>Seleccionar {label.toLowerCase()}</label>
      <select id={`${id}-select`} value="" onChange={choose} disabled={loading || Boolean(error)}>
        <option value="">{loading ? 'Buscando conceptos...' : 'Seleccionar un concepto'}</option>
        {options.filter((term) => !excludeIds.includes(term.id) && !selected.some((s) => s.id === term.id))
          .map((term) => <option key={term.id} value={term.id}>{term.label} · {term.code_system}: {term.code}</option>)}
      </select>
      {error && <p role="alert" className="catalog-error">{error}</p>}
      {!loading && !error && options.length === 0 && <p className="catalog-muted">No hay conceptos para esta búsqueda.</p>}
      {selected.length > 0 && <ul className="term-list">
        {selected.map((term) => <li key={term.id}>
          <span>{term.label}<small>{term.code_system}: {term.code}</small></span>
          <button type="button" className="catalog-text-button" aria-label={`Quitar ${term.label}`}
            onClick={() => onChange(selected.filter((item) => item.id !== term.id))}>Quitar</button>
        </li>)}
      </ul>}
    </fieldset>
  )
}
