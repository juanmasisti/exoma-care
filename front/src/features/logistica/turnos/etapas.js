// Etapas en orden; la clave la calcula el back (`stage`), acá solo va el texto para el paciente.
export const STAGES = [
  ['extraction', 'Extracción', 'Todavía no recibimos tu muestra. Se toma el día de tu turno de extracción.'],
  ['ready_for_pickup', 'Muestra lista para retirar', 'El centro tomó tu muestra y espera al transportista.'],
  ['to_lab', 'En camino al laboratorio', 'El transportista lleva tu muestra al laboratorio central.'],
  ['central_lab', 'En el laboratorio central', 'Tu muestra llegó y se prepara para el envío.'],
  ['to_korea', 'En viaje al laboratorio de análisis', 'Tu muestra viaja al laboratorio que hace el análisis.'],
  ['analysis', 'En análisis', 'Están analizando tu muestra.'],
  ['result_available', 'Resultado disponible', 'Ya está el resultado de tu estudio.'],
]
export const stageTitle = (stage) => stage === 'resample' ? 'Hay que repetir la extracción'
  : STAGES.find(([key]) => key === stage)?.[1] ?? 'En proceso'
