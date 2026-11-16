import { useEffect, useState } from 'react'
import { errorMessage } from '../../../services/api.js'
import { fetchPatologiasCatalogo } from '../../../services/bioinformaticaService.js'

export default function PatologiaSelect({ value, onChange, id = 'bioinformatics-pathology', required = false }) {
  const [pathologies, setPathologies] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    let active = true
    async function loadCatalog() {
      try {
        const catalog = await fetchPatologiasCatalogo()
        if (active) setPathologies(catalog)
      } catch (failure) {
        if (active) setError(errorMessage(failure))
      } finally {
        if (active) setLoading(false)
      }
    }
    loadCatalog()
    return () => { active = false }
  }, [])

  return (
    <div className="bioinformatics-pathology-select">
      <label htmlFor={id}>Patología</label>
      {loading
        ? <p role="status">Cargando catálogo de patologías...</p>
        : error
          ? <p role="alert">{error}</p>
          : <select id={id} value={value} onChange={onChange} required={required}>
            <option value="">Seleccioná una patología</option>
            {pathologies.map((item) => (
              <option key={item.codigo} value={item.codigo}>
                {item.nombre} ({item.codigo})
              </option>
            ))}
          </select>}
    </div>
  )
}
