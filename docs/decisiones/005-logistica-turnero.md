# Logística: centros y turnero (EC-15)

Rama: feature/turnos-extraccion (T00 y T01) y feature/turnos-reserva (T02), iniciadas desde
develop. Responsable: Ivo.
Esta decisión reúne las entregas del turnero; cada tarea completa su sección.

## T00a: reglas del turnero

Fecha: 2026-10-30.

- Las reglas puras están en `back/app/domain/entities/logistics.py`. Los turnos son cada
  15 minutos, de 9 a 18 (el último a las 17:45), de lunes a viernes y sin feriados.
- Zona horaria `America/Argentina/Buenos_Aires`. Se agregó `tzdata` a `requirements.txt`
  porque en Windows `zoneinfo` no trae las zonas.
- Un turno que empieza justo en la hora actual ya no se ofrece. La hora actual tiene que
  indicar la zona.
- `fixed_national_holidays` calcula solo los feriados inamovibles de la Ley 27.399,
  incluidos Carnaval y Viernes Santo, que dependen de Pascua. No calcula los trasladables
  (17/6, 17/8, 12/10 y 20/11) ni los puentes turísticos, porque dependen de un decreto
  anual. El Jueves Santo es día no laborable, no feriado.
- Si el Viernes Santo coincide con el 24/3 o el 2/4 (por ejemplo, en 2021), el día queda
  una sola vez con una sola descripción. El turnero lo bloquea igual; solo se pierde el
  nombre del otro feriado.

## T00b: provincias, centros y feriados

Fecha: 2026-10-30. Migración `0004`.

- Tablas `provinces` (nombre único), `extraction_centers` (nombre único por provincia,
  índice en `province_id`, `active` verdadero por defecto) y `holidays` (el día es la clave).
  Los centros son tercerizados y no son usuarios del sistema.
- Seed optativo y repetible `seed_demo_extraction_centers`. Las 24 jurisdicciones y sus
  capitales son reales y las coordenadas, aproximadas. Los nombres, direcciones y teléfonos
  de los centros son ficticios y dicen "DEMO". Las coordenadas de cada centro son las de su
  capital, desplazadas 0,002° (unos 200 m) por centro para que no se superpongan en el mapa.
  Cada provincia indica en el JSON (`offset`) hacia dónde se desplazan, para alejarse de
  ríos, lagunas y costas. Se verificó con OpenStreetMap que ninguno cae en el agua y que
  todos quedan dentro de su ciudad. CABA usa "Ciudad de Buenos Aires" como ciudad, para no
  confundirla con la provincia de Buenos Aires.
- **El reparto de los 100 centros por provincia es un dato DEMO, no una regla.** Las
  fuentes no lo indican. Se repartieron en forma aproximada según la población: Buenos Aires
  20, CABA 10, Córdoba y Santa Fe 8, Mendoza 5, Tucumán 4, nueve provincias con 3 y nueve
  con 2.
- El seed carga los feriados fijos del año actual y del siguiente. Los trasladables y los
  puentes se pueden cargar a mano en `holidays`. El seed agrega lo que falta y no modifica
  ni borra nada: conserva un centro desactivado y un feriado con otra descripción.
- Si otra rama también usa la migración `0004`, se resuelve con `alembic merge` al integrar.

## T00c: API de centros y horarios libres

Fecha: 2026-10-30. Sin migración nueva. Contrato en [logistica.md](../logistica.md).

- `GET /api/provinces`, `GET /api/extraction-centers` y
  `GET /api/extraction-centers/{id}/slots`. Son solo de consulta y los usa la pantalla del
  paciente para elegir centro y horario.
- **Permisos:** solo el rol `patient`. Los demás roles se suman cuando una tarea los
  necesite. Todavía no se exige que el paciente tenga un estudio habilitado: eso llega con
  la reserva y el vínculo usuario → paciente.
- **Feriados:** salen solo de la tabla `holidays`. No se vuelven a calcular con
  `fixed_national_holidays`. Un feriado que no esté cargado no se bloquea, por eso el seed
  se vuelve a correr cada año. La respuesta trae la descripción del feriado.
- **Hora actual:** la API la obtiene con la dependencia `get_clock`, en la zona de
  Buenos Aires, y las pruebas la reemplazan. Los turnos que ya empezaron no se ofrecen.
- **Búsqueda:** `q` busca en el nombre y la ciudad del centro, no en la dirección (en los
  datos DEMO todas son "Calle DEMO n"). En SQLite, `lower()` solo pasa a minúscula las
  letras ASCII, igual que en pacientes. Con centros reales, un nombre que empiece con Á o Ñ
  no aparecería al buscarlo en minúscula. Con los datos DEMO no pasa.
- Las provincias sin centros activos se listan igual, con `active_centers` en 0.
- Todavía no se descuentan los turnos reservados: las reservas llegan en T02 (hecho en T02a).

## T01: pantalla del paciente para elegir centro y horario

Fecha: 2026-11-01. Solo front. Ruta `/paciente/turnos/reservar`, únicamente para el rol
`patient`. Médico y gerente vuelven a su inicio; sin sesión se vuelve al login.

- **Mapa:** se agregó `leaflet` 1.9.4, sin `react-leaflet` (para un mapa con marcadores no
  hace falta). Se carga con `import()` dentro del efecto, así queda en un archivo aparte y no
  se descarga hasta que hay centros que mostrar. Al desmontar se llama a `map.remove()`, y si
  la carga termina después de desmontar no se crea el mapa (en desarrollo, `StrictMode` monta
  los efectos dos veces). Se usan `circleMarker` para evitar los íconos de imagen, que Vite
  no resuelve sin configuración extra. Si Leaflet no carga, queda la lista.
- **Mosaicos:** OpenStreetMap (`tile.openstreetmap.org`) con su atribución. Su política de
  uso alcanza para un uso académico de poco tráfico; en producción habría que usar un
  proveedor de mosaicos propio o contratado.
- Descartados: `iframe` de OpenStreetMap (un solo marcador, no se puede elegir desde el
  mapa), MapLibre (mucho más pesado) y Google Maps (pide clave y facturación; el repo es
  público).
- **Centros:** se ordenan en el front con orden natural ("Centro 2" antes que "Centro 10").
  Se paginan en el front porque llegan todos en un pedido: 8 por página por defecto, 12 o
  todos. La paginación copia la forma de la de `PatientsList` y usa sus clases de
  `patients.css`, sin modificarlas. Elegir en el mapa un centro de otra página salta a esa
  página. Las tarjetas son `<button aria-pressed>` para poder elegir con teclado; el mapa
  no se maneja con teclado.
- **Calendario:** sábados, domingos y días anteriores a hoy deshabilitados. La fecha que se
  pide al back se arma con año, mes y día del calendario, no con `toISOString()` (que pasa a
  UTC y después de las 21 da el día siguiente). Los feriados se informan recién al elegir el
  día ("Feriado: …"), porque no hay un endpoint que liste los feriados de un mes.
  "Hoy" sale del reloj y la zona del equipo del paciente, y se actualiza al elegir centro o
  día. Si el equipo tiene otra zona o la hora mal, el back manda igual: un día pasado
  devuelve la lista vacía y se ve "No hay turnos libres".
- **Horarios:** la hora se lee del ISO que devuelve el back, que ya viene en hora de
  Argentina, así no depende de la zona del navegador.
- **Confirmar turno:** deshabilitado con la leyenda "Disponible cuando se habilite la
  reserva" hasta T02 (falta la tabla `studies`). Habilitado en T02a.
- **`ClinicalLayout`:** se agregó la rama del rol `patient` (rótulo "Paciente", ítem
  "Reservar turno", textos del menú, avatar, perfil y miga de pan, y sin el enlace al
  catálogo). El cambio es solo aditivo: para médico y gerente no cambia nada. **Avisarle a
  Juanma en el PR**, porque el componente es compartido. `/portal` muestra al paciente un
  enlace a la reserva.
- Fuera de alcance: el stepper de los pasos del portal y "Volver a forma de pago" (todavía
  no existen los pasos 1 y 2 ni el estudio), y ayuno, horarios por centro, estacionamiento
  y distancias del prototipo.
- **Entorno:** el front necesita Node `^20.19.0` o `>=22.12.0`, lo que pide Vite 8. Con
  Node 20.14, npm no instala los binarios de rolldown y oxlint, y `npm test` no expande
  `tests/*.test.mjs`.

## T02a: reserva, cancelación y asistencia de turnos

Fecha: 2026-11-10. Rama `feature/turnos-reserva`, desde `develop`. Migración `0007`.
Contrato en [logistica.md](../logistica.md#turnos). Los PDF de la orden y el
consentimiento van en T02b.

- **Reglas:** en `logistics.py` se agregaron `AppointmentStatus` (`booked`, `cancelled`,
  `attended`, `absent`), sus transiciones (solo desde `booked`), `is_valid_slot` y el
  descuento de los reservados en `available_slots`. `is_valid_slot` acepta cualquier zona
  horaria: `10:00-03:00` y `13:00Z` son el mismo turno.
- **Tabla `appointments`:** `study_id` y `center_id` con FK, `starts_at`, `status`,
  `created_at`, `cancelled_at` y `study_status_before`. **`study_status_before` es un
  agregado a la tabla de la sección 3 del dominio:** guarda el estado del estudio antes de
  la reserva, para restaurarlo al cancelar. Las fechas se guardan en UTC con un
  `TypeDecorator` (`UTCDateTime`), porque SQLite descarta la zona sin convertir y el mismo
  turno con otra zona no chocaría en el índice. Una fecha sin zona se rechaza.
- **Unicidad:** dos índices únicos parciales donde `status = 'booked'`:
  `(center_id, starts_at)` y `(study_id)`. SQLite no respeta `SELECT ... FOR UPDATE`, así
  que el choque lo resuelve la base: el `IntegrityError` se traduce a 409. Para elegir el
  mensaje ("El estudio ya tiene un turno vigente." o "El horario ya está reservado en este
  centro.") se hace una consulta después, en vez de leer el texto del error, que cambia
  entre SQLite y PostgreSQL. Cancelar y registrar asistencia usan un `UPDATE ... WHERE
  status = 'booked'`: si dos pedidos cierran el mismo turno, el segundo recibe 409.
- **Dueño del estudio (PROVISORIO):** el repositorio de turnos lee, solo para consultar,
  `studies.patient_id` → `patients.usuario_id` y, en la misma consulta, `studies.status`
  (para `study_status_before`). No escribe en esas tablas. Se reemplaza cuando estudios y
  pacientes ofrezcan el dato por su servicio. Si el estudio no existe o es de otro paciente
  se responde 404, igual en los dos casos, para no revelar qué estudios existen.
- **Estudio no habilitado → 409**, no 422: el pedido es válido pero el estado del estudio
  no lo permite. Lo decide `estudio_habilitado`; logística no repite la regla.
- **Transacción:** el turno y el cambio de estado del estudio (`turno_sacado` al reservar,
  `study_status_before` al cancelar) se confirman juntos con una sola sesión por pedido.
  Para eso `cambiar_estado_estudio` dejó de hacer commit (ver la decisión 008): lo hace el
  caso de uso de turnos. Si el cambio de estado falla, no queda el turno.
- **Orden de las validaciones al reservar:** estudio propio (404), habilitado (409),
  centro activo (404), turno válido (422) y no pasado según `get_clock` (422).
- **404:** el caso de uso lanza su propia `NotFound` y la ruta traduce solo esa. Así un
  `KeyError` por un error de programación (también es `LookupError`) da 500 y no un 404.
- **Cancelar:** solo el dueño (un turno ajeno da 404) y solo si está `booked`; guarda
  `cancelled_at`. El horario vuelve a ofrecerse.
  - **No se puede cancelar un turno que ya empezó** según `get_clock` (409). Si no, el
    paciente que faltó podría cancelar antes de que se cargue la asistencia y esquivar la
    inasistencia. En "Día de extracción" el botón no se muestra en ese caso. **Regla
    decidida por Ivo, a confirmar con el profesor.**
  - Solo se restaura `study_status_before` si el estudio sigue en `turno_sacado`. Si otra
    etapa ya lo avanzó (por ejemplo, `listo_para_retirar` con el aviso de extracción de
    T03), se responde 409 y no se toca nada, para no hacerlo retroceder.
- **Asistencia:** solo `lab_administrator`, solo sobre un turno `booked`. Lleva el contador
  de inasistencias del paciente (`patient_absences`); la sanción sigue ABIERTA (decisión 7
  del dominio). No exige que el turno haya empezado: la ficha no lo pide.
- **Horarios libres:** `booked_starts` cuenta solo los `booked` del día de Buenos Aires
  (de 0 a 24 h de Argentina pasado a UTC).
- **Recordatorio:** fuera de T02. Lo agrega el servicio de avisos de Camila cuando exista;
  no se dejó código preparado.
- **Front:** "Confirmar turno" toma el estudio de `?estudio=ID` (PROVISORIO, hasta que
  estudios ofrezca la lista de estudios del paciente). Sin el parámetro se elige el estudio
  de una lista (ver el agregado de abajo, que reemplazó al botón deshabilitado con "Elegí el
  estudio para el que querés sacar turno"). Al confirmar se va a
  `/paciente/estudios/ID/turno` ("Día de extracción": fecha, hora, centro y "No requiere
  ayuno ni preparación especial"). Ante un 409 se muestra el mensaje del back y se vuelven a
  pedir los horarios del día (salvo que el estudio haya dejado de ser reservable: ver el
  agregado de abajo). Cancelar pide confirmación en la misma pantalla y vuelve a la
  reserva del mismo estudio.
- `reconcile_legacy_family_revision.py`: se sumaron `0007` y `appointments` a las
  constantes. **Avisarle a Juanma en el PR.**

### Agregado pedido por Ivo para la demo: mis turnos y elección de estudio

Sin migración. Al probar en el navegador faltaba cómo llegar a un turno o a un estudio sin
escribir la URL (que además cierra la sesión, porque se guarda en memoria: es del área de
Camila y no se tocó).

- `GET /api/appointments/mine` (solo `patient`): turnos `booked` del paciente, por fecha.
  Pantalla "Mis turnos" en `/paciente/turnos` e ítem "Mis turnos" en el menú del paciente.
- `GET /api/appointments/eligible-studies` (solo `patient`). **PROVISORIO:** lee, solo para
  consultar, los estudios propios sin turno vigente (`studies` → `patients.usuario_id`) y
  los filtra con `estudio_habilitado`. Se reemplaza por la lista de estudios del paciente
  de Tomás cuando exista. En la reserva sin `?estudio` se elige uno de esa lista.
- **Código del estudio (PROVISORIO):** `study_code` arma `EST-000001` con el id. Lo traen
  las respuestas de turnos y la lista de estudios. Se reemplaza si estudios define su código.
- **Con `?estudio=ID`** la reserva primero mira si el estudio está en `eligible-studies`:
  - Si está, muestra el formulario.
  - Si no está y tiene turno, avisa "Ya tenés un turno para este estudio" y enlaza a su día
    de extracción.
  - Si no está y no tiene turno, dice "Este estudio no está habilitado para sacar turno",
    con un enlace para elegir otro. Es el mismo mensaje para un estudio inexistente, ajeno
    o sin pagar, para no revelar qué estudios existen.
  - No se lee el texto del 404 del back para distinguir los casos.
- **Ante un 409 al confirmar** se repite esa consulta. Si el estudio dejó de ser
  reservable (por ejemplo, porque se reservó desde otra pestaña), se muestra ese estado. Si
  sigue siéndolo, el 409 fue por el horario: se muestra el mensaje del back y se vuelven a
  pedir los horarios del día.
- "Confirmar turno" deshabilitado siempre dice qué falta (centro, día u horario).
- La miga de pan dice "Mis turnos" en la lista y "Mis turnos › Día de extracción" en el día
  de extracción. La reserva sin estudios habilitados enlaza a "Ver mis turnos".
- `ClinicalLayout`: ítem "Mis turnos" (con `end`, para que no quede marcado junto con
  "Reservar turno") y miga de pan según la ruta, solo en la rama del paciente. **Avisarle a
  Juanma en el PR.**

## Pendiente

- PDF de la orden de extracción y del consentimiento (T02b).
- Si registrar la asistencia tiene que esperar a que empiece el turno.
- Confirmar con el profesor que no se puede cancelar un turno que ya empezó.
- **Para T03:** al cancelar se lee el estado del estudio y después se escribe
  `study_status_before` sin condición. Hoy nadie más cambia ese estado. Pero si el aviso de
  extracción lo cambia entre esa lectura y esa escritura, el estudio retrocedería. Cuando
  exista T03, la escritura tendría que exigir el estado anterior (`WHERE status =
  'turno_sacado'`) y responder 409 si no actualiza ninguna fila. Coordinarlo con Tomás.
- Quién carga cada año los feriados trasladables, los puentes y los feriados fijos de los
  años siguientes (hoy: volver a correr el seed y cargar el resto a mano).
- Con cuánta anticipación máxima se puede pedir turno. Las fuentes no lo indican, así que
  no hay límite. Hay que preguntarle al PO.
- Si el calendario tiene que mostrar los feriados deshabilitados antes de elegir el día:
  haría falta un endpoint de feriados por mes.
