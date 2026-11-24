// Base (decisión 016): T06 reemplaza este archivo con la autorización, el CSV, el PDF y el retiro de FedEx.
// Existe vacío para que el detalle del lote (T05) lo use sin esperar a T06.
// Props: session, sampleSetId y onChange() para avisarle al detalle que recargue el lote.
export default function EnvioLote() {
  return <section className="turnos-card" aria-label="Envío del lote">
    <h2>Envío</h2>
    <p className="turnos-empty">En construcción.</p>
  </section>
}
