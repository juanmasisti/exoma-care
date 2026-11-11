// Fecha y hora salen del ISO del back, que ya viene en hora de Argentina; así no dependen de la zona del navegador.
export function dateLabel(iso) {
  const [year, month, day] = iso.slice(0, 10).split('-').map(Number)
  return new Date(year, month - 1, day).toLocaleDateString('es-AR', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' })
}

export function timeLabel(iso) {
  return `${iso.slice(11, 16)} h`
}
