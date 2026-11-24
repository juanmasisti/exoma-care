import { useEffect, useRef, useState } from 'react'

const LINE = { color: '#5545ef', weight: 3, opacity: 0.8, dashArray: '6 6' }

// Recorrido en el orden fijo: Laboratorio Central → centros → Laboratorio Central. Mismo armado que CentersMap.
export default function RecorridoMap({ lab, stops }) {
  const element = useRef(null)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    let active = true
    let map
    Promise.all([import('leaflet'), import('leaflet/dist/leaflet.css')]).then(([{ default: L }]) => {
      if (!active) return
      map = L.map(element.current)
      L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
        maxZoom: 19, attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
      }).addTo(map)
      const labPoint = [lab.latitude, lab.longitude]
      const points = [labPoint, ...stops.map((stop) => [stop.center.latitude, stop.center.longitude]), labPoint]
      L.polyline(points, LINE).addTo(map)
      L.marker(labPoint, { icon: icon(L, 'LC', 'lab') }).bindTooltip('Laboratorio Central').addTo(map)
      for (const stop of stops) {
        const state = stop.picked_up_at ? 'done' : 'pending'
        // Nodo de texto: el nombre del centro no se interpreta como HTML.
        L.marker([stop.center.latitude, stop.center.longitude], { icon: icon(L, stop.picked_up_at ? '✓' : stop.sequence, state) })
          .bindTooltip(document.createTextNode(`${stop.sequence}. ${stop.center.name}`)).addTo(map)
      }
      map.fitBounds(points, { padding: [24, 24], maxZoom: 15 })
    }).catch(() => { if (active) setFailed(true) })
    return () => { active = false; map?.remove() }
  }, [lab, stops])

  if (failed) return <p className="turnos-empty">No se pudo cargar el mapa. Seguí la lista de paradas.</p>
  return <div ref={element} className="turnos-map transporte-map" role="region" aria-label="Mapa del recorrido" />
}

function icon(L, label, state) {
  return L.divIcon({ className: '', html: `<span class="transporte-pin transporte-pin-${state}">${label}</span>`, iconSize: [30, 30], iconAnchor: [15, 15] })
}
