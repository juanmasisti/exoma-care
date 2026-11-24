// Estados del lote en el orden en que avanza (SampleSetStatus del back).
export const SAMPLE_SET_STATUSES = [
  ['assembling', 'Armándose'],
  ['closed', 'Cerrados'],
  ['awaiting_pickup', 'Esperando retiro'],
  ['in_transit_to_sequencing_lab', 'En viaje'],
]

const LABELS = {
  assembling: 'Armándose',
  closed: 'Cerrado',
  awaiting_pickup: 'Esperando retiro',
  in_transit_to_sequencing_lab: 'En viaje al laboratorio de secuenciación',
}

export function statusLabel(status) {
  return LABELS[status] ?? status
}
