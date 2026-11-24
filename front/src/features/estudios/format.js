const MONEY = new Intl.NumberFormat('es-AR', { style: 'currency', currency: 'USD' })

// Los importes del backend viajan en centavos enteros.
export function money(cents) { return cents === null || cents === undefined ? '—' : MONEY.format(cents / 100) }

export function percentLabel(value) {
  return value === null || value === undefined ? '—' : `${Number(value).toLocaleString('es-AR', { maximumFractionDigits: 2 })}%`
}

export function dateTime(value) {
  if (!value) return '—'
  return new Date(value).toLocaleString('es-AR', { dateStyle: 'medium', timeStyle: 'short' })
}

export const STATUS_LABELS = {
  creado: 'Creado',
  pendiente_pago: 'Pendiente de pago',
  pendiente_autorizacion: 'Pendiente de autorización',
  pagado: 'Pagado',
  autorizado: 'Autorizado',
  rechazado: 'Cobertura rechazada',
  turno_sacado: 'Turno sacado',
  listo_para_retirar: 'Listo para retirar',
  requiere_remuestreo: 'Requiere remuestreo',
  en_viaje_a_corea: 'En viaje',
  en_area_bioinformatica: 'En bioinformática',
  en_analisis: 'En análisis',
  resultado_disponible: 'Resultado disponible',
}
export function statusLabel(status) { return STATUS_LABELS[status] || status }

export const STATUS_TONES = {
  creado: 'neutral',
  pendiente_pago: 'warning',
  pendiente_autorizacion: 'warning',
  pagado: 'success',
  autorizado: 'success',
  rechazado: 'danger',
}
export function statusTone(status) { return STATUS_TONES[status] || 'info' }

export const COUPON_STATUS_LABELS = {
  disponible: 'Disponible',
  medico: 'Asignado a médico',
  paciente: 'Asignado a paciente',
  canjeando: 'Canje en curso',
  usado: 'Usado',
}

// Precio acordado con el PO: USD 500 hasta 5 genes, más USD 30 por cada gen adicional.
// Un reanálisis (EC-14) tiene un 30 % de descuento; el importe oficial lo calcula el backend.
export const REANALYSIS_DISCOUNT_PERCENT = 30
export function estimateTotalCents(geneCount, reanalysis = false) {
  if (geneCount <= 0) return 0
  const gross = 50000 + Math.max(0, geneCount - 5) * 3000
  return reanalysis ? gross - Math.round(gross * REANALYSIS_DISCOUNT_PERCENT / 100) : gross
}
