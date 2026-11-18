import { useEffect, useMemo, useRef, useState } from 'react'
import { errorMessage } from '../../../services/api.js'
import { fetchPatologiasCatalogo } from '../../../services/bioinformaticaService.js'

const PAGE_SIZE = 25

export default function PatologiaSelect({ value, onChange, id = 'bioinformatics-pathology', required = false }) {
  const [pathologies, setPathologies] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [query, setQuery] = useState('')
  const [page, setPage] = useState(0)
  const [editing, setEditing] = useState(false)
  const inputRef = useRef(null)

  useEffect(() => {
    let active = true
    async function loadCatalog() {
      try {
        const catalog = await fetchPatologiasCatalogo()
        if (!Array.isArray(catalog)) {
          throw new TypeError('El catálogo de patologías devolvió un formato inválido.')
        }
        if (active) {
          setPathologies(catalog.filter((item) => (
            typeof item?.codigo === 'string'
            && typeof item?.nombre === 'string'
            && item.codigo.trim()
            && item.nombre.trim()
          )))
          setError('')
        }
      } catch (failure) {
        if (active) setError(errorMessage(failure))
      } finally {
        if (active) setLoading(false)
      }
    }
    loadCatalog()
    return () => { active = false }
  }, [])

  const selectedPathology = pathologies.find((item) => item.codigo === value)
  const selectedLabel = selectedPathology
    ? `${selectedPathology.nombre} (${selectedPathology.codigo})`
    : ''
  const selectionIsCommitted = Boolean(
    selectedPathology && query === selectedLabel,
  )
  useEffect(() => {
    inputRef.current?.setCustomValidity(
      required && !value ? 'Seleccioná una patología del catálogo.' : '',
    )
  }, [required, value])

  const filteredPathologies = useMemo(() => {
    const normalizedQuery = query.trim().toLocaleLowerCase()
    if (!normalizedQuery) return pathologies
    return pathologies.filter((item) => (
      `${item.nombre} ${item.codigo}`.toLocaleLowerCase().includes(normalizedQuery)
    ))
  }, [pathologies, query])
  const pageCount = Math.ceil(filteredPathologies.length / PAGE_SIZE)
  const visiblePathologies = filteredPathologies.slice(
    page * PAGE_SIZE,
    (page + 1) * PAGE_SIZE,
  )

  function changeQuery(event) {
    setQuery(event.target.value)
    setPage(0)
    setEditing(true)
    onChange({ target: { value: '' } })
    inputRef.current?.setCustomValidity(
      required ? 'Seleccioná una patología del catálogo.' : '',
    )
  }

  function choosePathology(item) {
    setQuery(`${item.nombre} (${item.codigo})`)
    setEditing(false)
    onChange({ target: { value: item.codigo } })
  }

  function handleKeyDown(event) {
    if (event.key === 'Escape') {
      setEditing(false)
      setQuery(selectedLabel)
    }
    if (event.key === 'Enter' && editing && visiblePathologies.length > 0) {
      event.preventDefault()
      choosePathology(visiblePathologies[0])
    }
  }

  async function retryCatalog() {
    setError('')
    setLoading(true)
    try {
      const catalog = await fetchPatologiasCatalogo()
      if (!Array.isArray(catalog)) {
        throw new TypeError('El catálogo de patologías devolvió un formato inválido.')
      }
      setPathologies(catalog.filter((item) => (
        typeof item?.codigo === 'string'
        && typeof item?.nombre === 'string'
        && item.codigo.trim()
        && item.nombre.trim()
      )))
    } catch (failure) {
      setError(errorMessage(failure))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="bioinformatics-pathology-select">
      <label htmlFor={id}>Patología</label>
      {loading
        ? <p role="status">Cargando catálogo de patologías...</p>
        : error
          ? <div><p role="alert">{error}</p><button type="button" onClick={retryCatalog}>Reintentar carga</button></div>
          : <>
            <input
              id={id}
              ref={inputRef}
              type="text"
              value={!editing && selectedLabel ? selectedLabel : query}
              onChange={changeQuery}
              onFocus={() => setEditing(true)}
              onKeyDown={handleKeyDown}
              placeholder="Buscar por nombre o código"
              maxLength={100}
              autoComplete="off"
              role="combobox"
              aria-autocomplete="list"
              aria-expanded={editing}
              aria-controls={`${id}-options`}
              required={required}
            />
            {editing && !selectionIsCommitted && <>
              <ul id={`${id}-options`} className="bioinformatics-pathology-options" role="listbox" aria-label="Patologías disponibles">
                {visiblePathologies.map((item) => (
                  <li key={item.codigo} role="option" aria-selected={item.codigo === value}>
                    <button type="button" onClick={() => choosePathology(item)}>
                      {item.nombre} ({item.codigo})
                    </button>
                  </li>
                ))}
                {visiblePathologies.length === 0 && <li className="bioinformatics-pathology-no-results">No se encontraron patologías.</li>}
              </ul>
              <div className="bioinformatics-pathology-pagination">
                <span>
                  {filteredPathologies.length === 0
                    ? '0 patologías'
                    : `Mostrando ${page * PAGE_SIZE + 1}-${Math.min((page + 1) * PAGE_SIZE, filteredPathologies.length)} de ${filteredPathologies.length}`}
                </span>
                {pageCount > 1 && <div>
                  <button type="button" onClick={() => setPage((current) => Math.max(0, current - 1))} disabled={page === 0}>
                    Anterior
                  </button>
                  <span>Página {page + 1} de {pageCount}</span>
                  <button type="button" onClick={() => setPage((current) => Math.min(pageCount - 1, current + 1))} disabled={page + 1 >= pageCount}>
                    Siguiente
                  </button>
                </div>}
              </div>
            </>}
          </>}
    </div>
  )
}
