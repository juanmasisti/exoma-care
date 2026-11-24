import { statusLabel } from './estados.js'
import { dateLabel, timeLabel } from '../turnos/fecha.js'

// Igual que SAMPLE_SET_SIZE del back (logistics.py).
const SAMPLE_SET_SIZE = 10

export function Badges({ sampleSet }) {
  return <div className="lotes-badges"><span className="turnos-badge">{statusLabel(sampleSet.status)}</span>
    {sampleSet.is_urgent && <span className="turnos-badge turnos-badge-alert">Pompe urgente</span>}</div>
}

export function Dates({ sampleSet, count }) {
  return <dl>
    <dt>Muestras</dt><dd>{count} de {SAMPLE_SET_SIZE}</dd>
    <dt>Abierto</dt><dd>{dateLabel(sampleSet.created_at)}, {timeLabel(sampleSet.created_at)}</dd>
    {sampleSet.closed_at && <><dt>Cerrado</dt><dd>{dateLabel(sampleSet.closed_at)}, {timeLabel(sampleSet.closed_at)}</dd></>}
  </dl>
}
