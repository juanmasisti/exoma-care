import { useEffect, useRef, useState } from 'react'

const MARKER = { radius: 8, color: '#4f46e5', weight: 2, fillColor: '#fff', fillOpacity: 1 }
const SELECTED = { radius: 11, color: '#4338ca', weight: 3, fillColor: '#4f46e5', fillOpacity: 1 }

export default function CentersMap({ centers, centerId, onChoose }) {
  const element = useRef(null)
  const markers = useRef(new Map())
  // Último onChoose, para no recrear el mapa en cada render.
  const choose = useRef(onChoose)
  const [ready, setReady] = useState(false)
  const [failed, setFailed] = useState(false)

  useEffect(() => { choose.current = onChoose }, [onChoose])

  useEffect(() => {
    let active = true
    let map
    const created = new Map()
    markers.current = created
    // Leaflet se carga recién acá porque lee window al importarse.
    Promise.all([import('leaflet'), import('leaflet/dist/leaflet.css')]).then(([{ default: L }]) => {
      if (!active) return
      map = L.map(element.current)
      L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
        maxZoom: 19, attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
      }).addTo(map)
      for (const center of centers) {
        created.set(center.id, L.circleMarker([center.latitude, center.longitude], MARKER)
          .bindTooltip(center.name).on('click', () => choose.current(center.id)).addTo(map))
      }
      map.fitBounds(centers.map((center) => [center.latitude, center.longitude]), { padding: [24, 24], maxZoom: 15 })
      setReady(true)
    }).catch(() => { if (active) setFailed(true) })
    return () => { active = false; setReady(false); created.clear(); map?.remove() }
  }, [centers])

  useEffect(() => {
    if (!ready) return
    markers.current.forEach((marker, id) => marker.setStyle(id === centerId ? SELECTED : MARKER))
  }, [ready, centerId])

  if (failed) return <p className="turnos-empty">No se pudo cargar el mapa. Elegí el centro de la lista.</p>
  return <div ref={element} className="turnos-map" role="region" aria-label="Mapa de centros de extracción" />
}
