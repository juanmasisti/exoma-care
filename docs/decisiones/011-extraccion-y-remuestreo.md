# Aviso de extracción y remuestreo (T03, EC-16)

Fecha: 13/11/2026. Área de logística (Ivo).

## Qué se hizo

- Dominio (`logistics.py`): `SampleStatus` y sus transiciones, `sample_is_usable` (mínimo
  2 ml, con `Decimal`), `initial_sample_status` y `study_id_from_code` (inversa de `study_code`).
- Tablas `extraction_notices`, `samples` y `sample_events` (migración `0008`), con índice único
  parcial `(study_id)` donde `is_current`. Se sumaron a `TABLES_AFTER_0005` y
  `REVISIONS_AFTER_0005` de `reconcile_legacy_family_revision.py`: **avisarle a Juanma en el PR**.
- `POST /api/webhooks/extraction` (bot), `GET /api/studies/{id}/tracking` (paciente) y
  `ExtractionService.solicitar_remuestreo` (para bioinformática). Contrato en
  [logística](../logistica.md#extracción-y-remuestreo-t03).
- Simulación del bot: `back/scripts/simular_aviso_extraccion.py`.

## Qué se decidió

- **Autenticación del bot con secreto compartido** (`X-Webhook-Secret`), comparado con
  `hmac.compare_digest`. El bot no es un usuario: sin JWT ni roles. Sin secreto configurado
  (o vacío), el webhook responde 401 a todo, para que no quede abierto por olvido.
- **Identificación del estudio** (decisión abierta 4 del dominio): el código impreso en la
  orden, hoy `EST-000001` (provisorio). Solo se acepta la forma exacta que genera `study_code`
  (sin ceros de más ni dígitos de otros alfabetos). Si estudios define otro código, cambia
  `study_id_from_code` y el webhook.
- **Volumen en el aviso** (decisión abierta 8): se toma del aviso. Pydantic rechaza NaN,
  infinito, 0, negativos y más de 2 decimales (1,999 no se redondea a 2,00).
- **Crear la muestra no es una transición.** Con menos de 2 ml nace `discarded` y no vigente,
  sin pasar por `ready_for_pickup`. `SAMPLE_TRANSITIONS` solo rige los cambios de una muestra
  que ya existe (`initial_sample_status`, con prueba).
- **El aviso marca `attended` el turno `booked`**: prueba que el paciente fue, y sin cerrarlo el
  índice único de turnos impediría sacar el turno del remuestreo. Si el último turno no
  cancelado ya está `attended`, se usa ese; si está `absent` o no hay turno, 409. El cambio usa
  la misma actualización condicional de turnos.
- **Carrera cancelar contra aviso** (pendiente de T03 en la decisión 005): queda cerrada sin
  tocar estudios. Cancelar y el aviso pasan el mismo turno por la actualización condicional
  (`WHERE status = 'booked'`): gana uno solo y el otro recibe 409 sin confirmar nada.
- **Idempotencia** por `external_id` único. Un aviso repetido devuelve 200 con el resultado de
  la primera vez (el estado con el que nació la muestra, no el de hoy). Si el contenido
  difiere, se devuelve igual el original y queda un warning en el log. Un aviso rechazado
  (404, 409) no se guarda, así el bot puede reintentarlo.
- **Sin columna `processed`** en `extraction_notices`: el aviso y su muestra se confirman en la
  misma transacción, así que siempre valdría `true`. El motivo del remuestreo va en
  `sample_events.reason`. Sección 3 del dominio actualizada.
- **Avisos concurrentes distintos para el mismo estudio**: en SQLite el INSERT del aviso toma
  el lock de escritura y el segundo lee lo que confirmó el primero (409). En otro motor haría
  falta que el cambio de estado del estudio sea condicional; queda anotado en el código.
- **`requiere_remuestreo` habilita a sacar turno** (`ENABLED_STUDY_STATUSES` del provisorio de
  estudios): mismo estudio, sin volver a pagar. Si se cancela ese turno, el estudio vuelve a
  `requiere_remuestreo`.
- **Aviso a paciente y médico**: `ResampleNotifier` con una implementación PROVISORIA que solo
  escribe en el log (`LoggingResampleNotifier`). Se llama después del commit; si falla, se
  registra el error y no se deshace lo guardado.
- `solicitar_remuestreo` recibe `now` además de `(study_id, motivo)` para poder fijar la hora
  en las pruebas, y `actor_id` opcional para el historial.
- Lectura PROVISORIA de `studies.status` en el repositorio de muestras, hasta que estudios la
  ofrezca. El dueño del estudio se lee con el repositorio de turnos (decisión 005).

## Pendiente y abierto

- **Pregunta para el profesor (junto con "asistencia antes de la hora del turno", decisión
  005):** ¿la extracción tiene que ser el mismo día del turno? Hoy un aviso marca `attended`
  un turno `booked` aunque sea de otro día (por ejemplo, con un código mal tipeado), porque no
  se compara `taken_at` con `starts_at`. No se agregó la regla para no inventarla.
- **JSON malformado sin secreto**: FastAPI lee el cuerpo antes de chequear el secreto, así que
  un JSON roto sin secreto responde 422 y no 401 (comprobado). Un JSON válido sin secreto sí
  da 401. Se deja así.
- Servicio de avisos de Camila (EC-20): reemplazar `LoggingResampleNotifier` por `notificar`.
  Quién es el médico y cuál es el mail los resuelve ese servicio.
- Código del estudio (decisión abierta 4) y lectura de `studies`: provisorios hasta que
  estudios (Tomás) los ofrezca. Cambio de estado condicional, para no depender de SQLite.
- Pantalla de seguimiento del paciente (paso 5) con acceso a sacar turno nuevo: T03b.
