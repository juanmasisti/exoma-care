# Logística: centros de extracción, horarios y turnos (EC-15)

Implementación y reglas: [decisión 005](decisiones/005-logistica-turnero.md).

## Centros y horarios

Requiere JWT con rol `patient`.

| Método y ruta | Función |
| --- | --- |
| GET /api/provinces | Las 24 jurisdicciones, ordenadas por nombre, con `active_centers` (puede ser 0) |
| GET /api/extraction-centers?province_id=&q= | Centros activos, ordenados por nombre. `q` busca en nombre y ciudad, sin distinguir mayúsculas |
| GET /api/extraction-centers/{id}/slots?date=AAAA-MM-DD | Horarios libres del centro ese día |

Centro: `id`, `name`, `address`, `city`, `province_id`, `latitude`, `longitude` y `phone` (puede ser `null`).

Horarios, por ejemplo `GET /api/extraction-centers/1/slots?date=2026-12-08`:

```json
{"center_id": 1, "date": "2026-12-08", "business_day": false,
 "holiday": "Inmaculada Concepción de María", "slots": []}
```

En un día hábil, `slots` trae los turnos de 15 minutos de 9:00 a 17:45 con hora de
Argentina (`"2026-11-02T09:00:00-03:00"`). Los turnos que ya empezaron no se ofrecen y un
día pasado devuelve la lista vacía. Sábados, domingos y feriados de la tabla `holidays`
no tienen horarios. Los horarios con un turno reservado tampoco se ofrecen; al cancelarlo,
el horario vuelve a aparecer.

Errores:
- 401: sin sesión.
- 403: rol distinto de `patient`.
- 404: centro inexistente o inactivo.
- 422: `date` ausente o inválida (enviarla como AAAA-MM-DD), o `q` de más de 100 caracteres.

## Turnos

| Método y ruta | Rol | Función |
| --- | --- | --- |
| POST /api/appointments | `patient` | Reserva un turno para un estudio propio. 201 con el turno |
| DELETE /api/appointments/{id} | `patient` | Cancela un turno propio reservado. 204 |
| GET /api/studies/{id}/appointment | `patient` | Turno vigente de un estudio propio |
| GET /api/appointments/mine | `patient` | Turnos reservados del paciente, por fecha |
| GET /api/appointments/eligible-studies | `patient` | Estudios propios habilitados y sin turno vigente: `[{"id": 1, "code": "EST-000001", "status": "pagado"}]` (PROVISORIO) |
| PATCH /api/appointments/{id}/attendance | `lab_administrator` | Registra si el paciente asistió |

Reserva, por ejemplo:

```json
POST /api/appointments
{"study_id": 1, "center_id": 1, "starts_at": "2026-11-02T10:00:00-03:00"}
```

`starts_at` tiene que indicar la zona horaria. Respuesta (también la de
`GET /api/studies/{id}/appointment` y la de cada turno de `GET /api/appointments/mine`):

```json
{"id": 1, "study_id": 1, "study_code": "EST-000001", "starts_at": "2026-11-02T10:00:00-03:00", "status": "booked",
 "center": {"id": 1, "name": "Centro de extracción DEMO La Plata 1",
            "address": "Calle DEMO 1, La Plata", "city": "La Plata", "phone": "DEMO-0000-01"}}
```

Al reservar, el estudio pasa a `turno_sacado`; al cancelar, vuelve al estado que tenía.
Asistencia: `{"attended": true}` deja el turno en `attended` y `false` en `absent`. La
respuesta trae `patient_absences`, la cantidad de inasistencias del paciente.

Errores:
- 401: sin sesión.
- 403: rol no permitido.
- 404: el estudio no existe o no es del paciente; el turno no existe o es de otro paciente;
  el centro no existe o está inactivo; el estudio no tiene turno vigente.
- 409: el estudio no está pagado ni autorizado, ya tiene un turno vigente, o el horario ya
  está reservado en ese centro; cancelar o registrar asistencia de un turno que no está
  reservado; cancelar un turno que ya empezó, o cuyo estudio ya pasó a otra etapa.
- 422: horario que no es un turno válido (sábado, domingo, feriado, fuera de 9 a 17:45 o
  fuera de los 15 minutos), horario pasado, o `starts_at` sin zona horaria.

## Pantallas del paciente

Solo rol `patient`; código en `front/src/features/logistica/turnos/`.

- `/paciente/turnos`: "Mis turnos", con los turnos reservados y el enlace a cada día de
  extracción.
- `/paciente/turnos/reservar`: sin `?estudio`, el paciente elige entre sus estudios
  habilitados. Con `?estudio=ID` elige provincia, centro (en las tarjetas o en el mapa de
  OpenStreetMap), día y horario libre, y confirma el turno; si el estudio ya tiene turno, la
  pantalla lo avisa y enlaza a su día de extracción, y si no está habilitado (o no existe o
  es de otro paciente) lo informa sin mostrar el formulario. Si el horario se ocupó mientras elegía,
  ve el mensaje del back y los horarios del día se actualizan. Detalles en la [decisión 005](decisiones/005-logistica-turnero.md#t01-pantalla-del-paciente-para-elegir-centro-y-horario).
- `/paciente/estudios/ID/turno` ("Día de extracción"): fecha, hora y centro del turno, y
  cancelación con confirmación en la misma pantalla.

## Preparar y ejecutar (Git Bash)

Desde `back`:

```bash
./.venv/Scripts/python.exe -m alembic upgrade head
# Debe quedar en la cabeza que informa `alembic heads`. Carga opcional de provincias,
# 100 centros DEMO y feriados fijos (también migra antes de cargar):
./.venv/Scripts/python.exe -m seeders logistics
bash dev.sh
```

El seed carga los feriados del año actual y del siguiente. Al empezar cada año hay que
volver a correrlo. Los feriados trasladables y los puentes se cargan a mano en `holidays`.

## Verificación

`./.venv/Scripts/python.exe -m pytest -q` desde `back`. Las pruebas de la API están en
`tests/test_extraction_centers_api.py` y `tests/test_appointments_*.py` (reservar, cancelar,
asistencia y consultas del paciente, con el armado común en `tests/appointments_setup.py`), y
fijan la hora actual reemplazando `get_clock`.

Pantalla: `npm test` y `npm run lint` desde `front` (Node `^20.19.0` o `>=22.12.0`). Las
pruebas están en `front/tests/turnos-*.test.mjs`, una por pantalla (la reserva en dos:
horarios y confirmación), con el armado común en `front/tests/turnos-setup.mjs`, y fijan la
fecha con `mock.timers`.

## Recorridos (T04a, provisorio)

Cliente del módulo de optimización de recorridos (módulo 9, de otro grupo). Detalle en la
decisión `009-cliente-recorridos.md`.

Configuración en `back/.env` (si falta, se usan estos valores):

```
RECORRIDOS_API_URL=https://optimizacionapi.vercel.app/api/optimizacion
CENTRAL_LAB_LATITUDE=-34.921559
CENTRAL_LAB_LONGITUDE=-57.938362
```

El endpoint provisorio `POST /api/transport/route-preview` se borró en T04: los centros salen de la
orden del día (ver [Orden del día y transportista](#orden-del-día-y-transportista-t04)). El recorrido
sale del Laboratorio Central (Calle 62 N° 555, La Plata) y vuelve a él. Con un solo centro no se llama
al módulo.

Pruebas del cliente: `tests/test_transport_api.py` (con un doble del módulo; no salen a internet).

## Documentos del turno (T02b)

| Método y ruta | Rol | Función |
| --- | --- | --- |
| GET /api/appointments/{id}/documents/{kind} | `patient` | PDF de un turno propio reservado. `kind`: `order` (orden de extracción) o `consent` (consentimiento informado) |

Responde `application/pdf` con `Content-Disposition: attachment` y el nombre
`orden-EST-000001.pdf` o `consentimiento-EST-000001.pdf`. El PDF se genera en el momento
con `fpdf2` y no se guarda.

- Orden de extracción: código del estudio, fecha y hora en hora argentina, nombre y dirección
  del centro, nombre, apellido y DNI del paciente, y "No requiere ayuno ni preparación especial".
- Consentimiento informado: **texto PROVISORIO** y genérico con los datos del paciente y del
  estudio, aviso para menores (firma madre, padre o tutor) y líneas de firma. Se imprime, se
  firma y se entrega en papel; no se sube al sistema.

Errores:
- 401: sin sesión.
- 403: rol no permitido.
- 404: el turno no existe o es de otro paciente.
- 409: el turno no está reservado (cancelado, asistido o ausente).
- 422: `kind` distinto de `order` o `consent`.

En "Día de extracción" (`/paciente/estudios/ID/turno`), los botones "Descargar orden" y
"Descargar consentimiento" piden el PDF con `api` (axios, `responseType: 'blob'`), porque el
token viaja en el header `Authorization` y un enlace directo no lo manda. Si el back rechaza
la descarga, la pantalla muestra su mensaje.

Pruebas: `back/tests/test_appointments_documents.py` (contenido de los PDF, hora argentina y
permisos) y `front/tests/turnos-dia-extraccion.test.mjs`. Detalles y pendientes en la
[decisión 010](decisiones/010-documentos-del-turno.md).

## Clientes del envío a Corea (T06a)

Los usa el envío del lote ([T06](#envío-internacional-t06)); los endpoints provisorios
`/api/shipments/pickups` se borraron en T06.

- `FedExClient` manda `scheduled_at` a FedEx en hora argentina sin zona (`logistics.TIMEZONE`),
  como pide su contrato. El lugar es `CENTRAL_LAB_ADDRESS` (por defecto "Laboratorio Central,
  Calle 62 N° 555, La Plata").
- Si FedEx responde 400, 401, 404 o 5xx, tarda más de 5 s, no contesta o responde algo mal
  formado, el cliente lanza un error con el motivo en español (incluye el `error` de FedEx si viene).

Configuración en `back/.env` (nunca en el repo): `FEDEX_URL` (URL base del módulo 10),
`FEDEX_USER` y `FEDEX_PASS` (credenciales del grupo, Basic Auth).

El Ministerio de Salud no tiene endpoint: `SimulatedHealthMinistry` (SIMULADO) siempre
autoriza y devuelve un PDF con las filas del CSV.

Pruebas: `back/tests/test_shipment_clients.py` (`httpx.MockTransport`; no salen a internet).
Detalles en la [decisión 012](decisiones/012-clientes-envio.md).

## Extracción y remuestreo (T03)

| Método y ruta | Quién | Función |
| --- | --- | --- |
| POST /api/webhooks/extraction | El bot de extracción (sin usuario), con `X-Webhook-Secret` | Aviso de que el centro tomó la muestra |
| GET /api/studies/{id}/tracking | `patient` | Seguimiento de un estudio propio: muestras, historial y si requiere nueva extracción |

### Aviso de extracción

El bot no es un usuario del sistema: no manda token ni tiene rol. Se autentica con el secreto
compartido del header `X-Webhook-Secret`, que se compara con `EXTRACTION_WEBHOOK_SECRET` de
`back/.env`. Sin ese valor configurado, el webhook rechaza todo.

```json
{"external_id": "bot-123", "study_code": "EST-000001", "volume_ml": 2.5, "taken_at": "2026-11-13T10:15:00-03:00"}
```

- `external_id`: id del aviso en el bot (1 a 100 caracteres). Un aviso con el mismo id
  devuelve el mismo resultado sin duplicar nada.
- `study_code`: el código impreso en la orden de extracción (PROVISORIO, `EST-` + id).
- `volume_ml`: mililitros del tubo. Mayor que 0, finito, hasta 999,99 y con 2 decimales como
  máximo (1,999 se rechaza en vez de redondearse a 2,00).
- `taken_at`: fecha y hora de la extracción, con zona horaria.

Qué hace, todo en una transacción:

1. El estudio tiene que estar en `turno_sacado`.
2. El turno `booked` del estudio pasa a `attended`: el aviso prueba que el paciente fue. Si ya
   estaba `attended`, se usa ese.
3. Se crea la muestra vinculada al turno y al aviso:
   - 2 ml o más: `ready_for_pickup` y vigente; el estudio pasa a `listo_para_retirar`.
   - Menos de 2 ml: nace `discarded`, no vigente; el estudio pasa a `requiere_remuestreo` y se
     avisa por mail a paciente y médico (ver T03c).

Respuesta: 201 con `{"sample_id": 1, "sample_status": "ready_for_pickup", "study_status": "listo_para_retirar"}`.
Aviso repetido: 200 con el resultado de la primera vez.

Errores:
- 401: falta el secreto, no coincide o no está configurado (antes de validar los campos; un
  JSON mal formado da 422, ver decisión 011).
- 404: código con otra forma que `EST-000001` o estudio inexistente.
- 409: el estudio no está en `turno_sacado`; el último turno está `absent` o no hay turno;
  el turno cambió a la vez (por ejemplo, el paciente lo canceló); el estudio ya tiene una
  muestra vigente.
- 422: cuerpo inválido (volumen NaN, infinito, 0 o negativo; fecha sin zona; código vacío o
  de más de 20 caracteres).

Un aviso rechazado no queda guardado: el bot puede reintentarlo con el mismo `external_id`.

### Remuestreo

Por volumen insuficiente lo dispara el aviso. Por ADN insuficiente o desnaturalizado
(después de Corea), bioinformática llama al caso de uso
`ExtractionService.solicitar_remuestreo(study_id, motivo, now, actor_id=None)`; no hay
endpoint. La muestra vigente pasa a `discarded` y deja de ser vigente, el motivo queda en el
historial y el estudio pasa a `requiere_remuestreo`.

En los dos casos es **el mismo estudio** y **no se toca el pago**: `requiere_remuestreo`
habilita a sacar un turno nuevo, y el aviso de ese turno crea la muestra vigente nueva. Las
anteriores quedan en el historial.

### Seguimiento

`GET /api/studies/{id}/tracking` devuelve `study_id`, `code`, `status`,
`requires_new_extraction` y `samples` (cada una con `id`, `volume_ml`, `status`, `is_current` y
sus `events`: `from_status`, `to_status`, `reason`, `at` en hora argentina). 401 sin sesión, 403
con otro rol, 404 si el estudio no existe o es de otro paciente. La pantalla del paso 5 va en T03b.

### Simulación del bot

Ningún grupo tiene el bot: `back/scripts/simular_aviso_extraccion.py` (`SimulatedExtractionBot`)
hace el mismo POST que haría el bot real, con un `external_id` nuevo y la hora actual. Solo el
camino feliz. Con el back levantado y `EXTRACTION_WEBHOOK_SECRET` en `back/.env`, desde `back`:

```powershell
.\.venv\Scripts\python.exe -m alembic upgrade head   # incluye la 0008 (muestras)
.\.venv\Scripts\python.exe -m scripts.simular_aviso_extraccion EST-000001 2.5
```

Pruebas: `back/tests/test_extraction_api.py`, `back/tests/test_logistics_domain.py` y
`back/tests/test_migrations.py` (índice parcial de la `0008`).
Detalles y pendientes en la [decisión 011](decisiones/011-extraccion-y-remuestreo.md).

## Seguimiento del paciente (T03b)

| Método y ruta | Rol | Función |
| --- | --- | --- |
| GET /api/studies/tracking/mine | `patient` | Estudios propios con al menos una muestra: `study_id`, `code`, `status`, `stage`, `requires_new_extraction` |
| GET /api/studies/{id}/tracking | `patient` | Igual que en T03, ahora también con `stage` |

`/tracking/mine` existe porque, cuando llega el aviso de extracción, el turno pasa a `attended`
y "Mis turnos" (`/appointments/mine`, solo turnos reservados) deja de mostrarlo: sin esta lista,
el paciente no llegaría al seguimiento justo cuando la muestra está lista o hay que repetirla.
401 sin sesión y 403 con otro rol.

`stage` lo calcula el back (`tracking_stage` en `use_cases/extraction.py`). Los estados de
bioinformática salen de sus constantes (`BIOINFORMATICS_STATUSES` y `RESULT_AVAILABLE_STATUS`):

| `stage` | Texto para el paciente | Cuándo |
| --- | --- | --- |
| `extraction` | Extracción | Sin muestra vigente (todavía no se tomó o se sacó turno nuevo) |
| `ready_for_pickup` | Muestra lista para retirar | Muestra `ready_for_pickup` |
| `to_lab` | En camino al laboratorio | Muestra `with_transporter` |
| `central_lab` | En el laboratorio central | Muestra `received` o `in_sample_set` |
| `to_sequencing_lab` | En viaje al laboratorio de análisis | Muestra `in_transit_to_sequencing_lab` (antes `in_transit_to_korea`, decisión 016) |
| `analysis` | En análisis | Estudio en un estado de bioinformática |
| `result_available` | Resultado disponible | Estudio con el resultado disponible |
| `resample` | Hay que repetir la extracción | Estudio `requiere_remuestreo` |

### Pantalla

"Seguimiento" en `/paciente/estudios/ID/seguimiento` (solo `patient`; miga de pan "Mis turnos ›
Seguimiento"). Muestra la etapa actual con una explicación corta y la lista de etapas (hechas,
actual y por venir). En remuestreo, en lugar de la lista, explica que hay que repetir la extracción, que es el mismo
estudio y no se paga de nuevo, el motivo (el que cargó bioinformática o, si no hay, el volumen
mínimo de 2 ml) y el botón "Sacar turno nuevo", que lleva a la reserva con ese estudio elegido.
Las muestras descartadas quedan en "Muestras anteriores", con la fecha de la extracción y el
volumen. Estados de carga y de error con "Reintentar".

Se llega navegando dentro de la app (la sesión está en memoria y se pierde al escribir la URL):
- "Mis turnos": "Ver seguimiento" en cada turno y la sección "Seguimiento de tus estudios"
  (estudios ya extraídos). Esa sección carga aparte: si falla, la lista de turnos se sigue viendo
  y el error tiene su propio "Reintentar". Sin turnos pero con estudios en seguimiento, no
  muestra la invitación a reservar.
- "Día de extracción": "Ver seguimiento del estudio" (o "Ver seguimiento" cuando el estudio ya
  no tiene turno vigente).

Para probarlo en el navegador: reservar un turno, mandar el aviso con el simulador (sección
"Simulación del bot") y entrar desde "Mis turnos". Con `1.9` ml aparece el remuestreo; con
`2.5`, "Muestra lista para retirar".

Pruebas: `back/tests/test_extraction_api.py`, `front/tests/turnos-seguimiento.test.mjs` y
`front/tests/turnos-mis-turnos.test.mjs`.
Detalles en la [decisión 013](decisiones/013-seguimiento-paciente.md).

## Aviso de remuestreo por mail (T03c)

Cuando el estudio pasa a `requiere_remuestreo` (aviso con menos de 2 ml o
`solicitar_remuestreo`), después de confirmar los cambios se manda un mail con el servicio de
avisos de Camila (`EnviarNotificacionUseCase`, que también lo registra en `notification_logs`).
No hay endpoint nuevo.

- **Destinatarios**: `SQLAlchemyStudyRepository.notification_recipients`: el paciente (mail
  de su cuenta o, si no tiene, el de la ficha) y el médico que lo cargó, si hay y si su mail es
  distinto del del paciente. Sin mail del
  paciente no se manda y queda un warning en el log.
- **Asunto**: `Hay que repetir la extracción del estudio EST-000001`.
- **Mensaje**: el código del estudio, el motivo y que hay que sacar un turno nuevo desde el
  seguimiento, sin volver a pagar. Sin nombre, DNI ni otros datos del paciente.
- **`Idempotency-Key`**: `remuestreo-{study_id}-{sample_id}`; `referencia`: el id del estudio.
- **Si falla** (servicio caído o que rechace el pedido, o `NOTIFICATIONS_API_KEY` sin
  configurar), lo guardado no se deshace, el webhook responde igual 201 y el error queda en el
  log (`No se pudo avisar el remuestreo del estudio N.`). No se reintenta solo. Un rebote del
  mail llega después y no pasa por acá.

Para probar el envío real: `NOTIFICATIONS_API_KEY` (y, si cambia, `NOTIFICATIONS_BASE_URL`) en
`back/.env`, un paciente con un mail propio y un estudio con turno reservado. Con el back
levantado, como en [Simulación del bot](#simulación-del-bot), desde `back`, el simulador con
menos de 2 ml (si avisos tarda, el simulador puede cortar a los 5 s aunque el back responda
201: el resultado se ve en el log del back o en el seguimiento):

```powershell
.\.venv\Scripts\python.exe -m scripts.simular_aviso_extraccion EST-000001 1.9
```

Pruebas: `back/tests/test_extraction_api.py` (con un doble del caso de uso: ninguna sale a
internet). Detalles en la [decisión 014](decisiones/014-aviso-remuestreo.md).

## Simulador del bot de extracción (T03d)

SIMULACIÓN para demo y pruebas: el administrativo manda, desde la app, el mismo aviso que
mandaría el bot cuando un centro toma la muestra. Está apagado por defecto.

| Método y ruta | Rol | Función |
| --- | --- | --- |
| GET /api/demo/extraction-notice/studies | `lab_administrator` | Turnos reservados: `study_id`, `code`, `patient_name`, `center_name`, `starts_at` |
| POST /api/demo/extraction-notice | `lab_administrator` | Simula el aviso del bot para un estudio |

- **Interruptor**: `DEMO_TOOLS_ENABLED=true` en `back/.env` (por defecto `false`). Apagado, los
  dos endpoints responden 404 (antes de pedir sesión) y el menú no muestra la pantalla.
- **Aviso simulado**: cuerpo `{"study_code": "EST-000001", "volume_ml": 1.5}`. Se procesa con el
  mismo caso de uso que `POST /api/webhooks/extraction` (`ExtractionService.registrar_aviso`),
  con `external_id` `sim-<uuid>` y la hora actual como `taken_at`. Mismas reglas, misma
  respuesta (201 con `sample_id`, `sample_status`, `study_status`), mismos errores (404, 409,
  422) y el mismo mail de remuestreo (T03c). No usa el secreto del webhook.
- 401 sin sesión y 403 con otro rol.

### Pantalla

"Simular aviso del bot" en `/administrativo/simulador-bot` (solo `lab_administrator`), con la
etiqueta SIMULACIÓN. Se elige un estudio con turno reservado, se carga el volumen en ml y
"Enviar aviso" muestra el resultado en palabras: "Muestra lista para retirar" o "Hay que
repetir la extracción" (con el aviso por mail al paciente). El estudio avisado sale de la
lista porque su turno queda asistido. Estados: carga; error al cargar con "Reintentar" (salvo
apagado: "El simulador está apagado en este servidor."); error del envío con el mensaje del
back; y vacío.

El ítem del menú aparece solo si la lista responde: el front pregunta al back una vez por
sesión y no hay otro interruptor. Un cambio de `DEMO_TOOLS_ENABLED` se ve en el menú al recargar
la página o volver a iniciar sesión; si esa consulta falla, el ítem no aparece hasta entonces.

Turnos DEMO para el simulador: `python -m seeders logistics` (desde `back/`) deja a la paciente
DEMO (DNI 45000001) con 3 estudios con turno reservado. Cuenta sus turnos reservados y crea los
que falten, así que repone los que se usaron en el simulador y correrlo dos veces no duplica
nada. Cada estudio pasa por el flujo de estudios (solicitud de Fabry, presupuesto y pago
particular simulado) y por la reserva de turnos (10:00, primeros días hábiles libres, primer
centro DEMO). El catálogo de genes es fijo (Fabry, gen GLA): el seeder no consulta Apigen.

Para probarlo: `DEMO_TOOLS_ENABLED=true` en `back/.env` (vale desde el pedido siguiente, sin
reiniciar el back), reservar un turno
como paciente, entrar como administrativo y elegir "Simular aviso del bot". Con menos de 2 ml el
estudio queda en remuestreo y se manda el mail.

Pruebas: `back/tests/test_demo_extraction_api.py` y `front/tests/simulador-bot.test.mjs`.
Detalles en la [decisión 015](decisiones/015-simulador-bot.md).

## Base de transporte, lotes y envío (T04-base)

Deja lo común para hacer T04, T05 y T06 en paralelo, sin tocar archivos compartidos. Detalles en
la [decisión 016](decisiones/016-logistica-base.md).

- **Estados** (`back/app/domain/entities/logistics.py`): `DailyRouteStatus` (`pending` →
  `arrived`), `SampleSetStatus` (`assembling` → `closed` → `awaiting_pickup` →
  `in_transit_to_sequencing_lab`). El estado de muestra en viaje pasó a llamarse
  `in_transit_to_sequencing_lab` (la migración 0018 renombra los datos) y la etapa del seguimiento
  pasó a ser `to_sequencing_lab`.
- **Reglas puras**: `next_stop_sequence`, `sample_set_must_close`, `is_urgent_pompe` (por el
  código de patología `POMPE`) e `is_valid_pickup_time` (día hábil, de 9 a antes de las 18).
- **Tablas** (migración `0018`): `daily_routes`, `route_stops`, `route_pickups`, `sample_sets`
  (un solo lote `assembling` a la vez; el envío vive en el lote) y `sample_set_items` (slot 1 a 10).
- **Repositorios**: `SampleRepository.change_status` (compartido), `RouteRepository` (T04),
  `SampleSetRepository` (T05) y `ShipmentRepository` (T06).
- **Enganches**: `get_sample_set_assigner` (en `routes/sample_sets.py`: la llegada llama al armado
  de lotes) y `get_sample_set_closed_handler` (en `routes/shipments.py`: el cierre del lote llama a la
  autorización). Por ahora no hacen nada. Cada uno vive junto al router de la tarea que lo implementa.
  `TRANSPORT_ROLES` (`back/app/api/logistics_dependencies.py`) es provisorio: el administrativo hace de
  transportista hasta que exista el rol `transporter`.
- **Pantallas "En construcción"**: `/transporte/*`, `/administrativo/ordenes-del-dia`,
  `/administrativo/lotes` y `/administrativo/lotes/:id`, con sus ítems en el menú del
  administrativo.

Muestras DEMO para probar cada tarea por separado: `python -m seeders logistics` (desde `back/`)
también deja, para la paciente DEMO:

| Grupo | Muestras | Para |
| --- | --- | --- |
| `lista` | 5 `ready_for_pickup`: 4 en tres centros DEMO de La Plata (Buenos Aires) y 1 en Córdoba | T04 |
| `recibida` | 2 `received`, sin lote | T05 |
| `lote-armando` | 9 `in_sample_set` en un lote `assembling` | T05 |
| `lote-cerrado` | 10 `in_sample_set` en un lote `closed`, sin autorización | T06 |

Cada muestra pasa por el flujo real: estudio pagado, turno de hace uno o dos meses, aviso de
extracción con 4 ml y `change_status` paso a paso. Los eventos los firma la administrativa
porque todavía no hay rol transportista. No se guardan recorridos ni retiros. Un grupo ya
cargado no se repite, aunque sus muestras hayan avanzado después. Si un grupo quedó a medias, el
seeder lo avisa y no lo completa. Si ya hay un lote armándose, no carga los grupos con lote.

Pruebas: `back/tests/test_logistics_domain.py`, `back/tests/test_logistics_base.py`,
`back/tests/test_logistics_seeder.py` y `front/tests/logistica-base.test.mjs`.

## Orden del día y transportista (T04)

Cada día hábil, una orden por provincia con los centros activos que tienen muestras listas para retirar,
en el orden fijo que devuelve el módulo de recorridos. El transportista retira centro por centro y
registra la llegada al Laboratorio Central, que recibe las muestras y dispara el armado de lotes. Detalle
en la [decisión 017](decisiones/017-orden-del-dia.md).

`TRANSPORT_ROLES` es PROVISORIO: hoy es el administrativo (decisión 016).

| Endpoint | Rol | Respuesta |
| --- | --- | --- |
| `POST /api/transport/daily-routes` `{"date": "2026-11-02"}` | `lab_administrator` | 201 si creó alguna orden, 200 si ya estaban todas (no toca las existentes). Lista de órdenes del día |
| `GET /api/transport/daily-routes?date=` | `lab_administrator` | órdenes del día: `province`, `status`, `stops` y `picked_up` (avance) |
| `GET /api/transport/my-route?date=&province_id=` | `TRANSPORT_ROLES` | orden con `province`, `stops` en secuencia (centro, `picked_up_at`, `sample_codes`), `next_stop_id` y `on_board`. `province_id` es PROVISORIO |
| `POST /api/transport/daily-routes/{id}/stops/{stop_id}/pickup` | `TRANSPORT_ROLES` | comprobante: `center`, `picked_up_at` y `sample_codes` retirados |
| `POST /api/transport/daily-routes/{id}/arrival` | `TRANSPORT_ROLES` | `arrived_at` y `received_codes`. Llama a `SampleSetAssigner.asignar_a_sample_set` por cada muestra |

| Caso | Respuesta |
| --- | --- |
| Sábado, domingo o feriado | 422 con el motivo |
| El módulo de recorridos falla, tarda más de 5 s o devuelve un punto que no es de ningún centro | 502; no se guarda ninguna orden |
| `my-route` sin orden para esa provincia y fecha; parada que no es de la orden | 404 |
| Retirar un centro antes que el anterior, o retirarlo dos veces | 409 |
| Llegada con centros sin retirar, o registrada dos veces | 409 |
| Un centro se da de baja mientras se genera la orden | 409; no se guarda ninguna orden |
| Error inesperado del armado de lotes | 500; se deshace la llegada entera |
| Sin token / otro rol | 401 / 403 |

El retiro pasa a `with_transporter` las muestras listas del centro en ese momento y guarda cada una en
`route_pickups`. La llegada pasa a `received` exactamente esas. Las horas vienen en hora de Argentina.

Pantallas:

- `/administrativo/ordenes-del-dia`: fecha (hoy por defecto), "Generar órdenes" y cada provincia con
  su avance.
- `/transporte`: provincia (select PROVISORIO), resumen y siguiente centro. Desde ahí:
  - `/transporte/orden`: la secuencia completa; solo se abre el siguiente centro;
  - `/transporte/centro/:stopId` (id de la parada): confirmar el retiro y ver el comprobante;
  - `/transporte/a-bordo`: muestras a bordo, fin de recorrido y llegada.

Para probarlo con el seeder (`python -m seeders logistics`, grupo `lista`):

- entrá como el administrativo DEMO y generá la orden de un día hábil;
- en `/transporte`, elegí Buenos Aires (3 centros de La Plata) o Córdoba (1 centro);
- retirá en orden y registrá la llegada.

Mientras no esté T05, la llegada no arma lotes.

Pruebas: `back/tests/test_transport_api.py`, `front/tests/transportista-ordenes.test.mjs` y
`front/tests/transportista-recorrido.test.mjs` (armado común en `front/tests/transportista-setup.mjs`).

## Sample sets (T05)

Arma los lotes de 10 muestras solo, al registrar la llegada, y los cierra antes si llega un Pompe
urgente. Detalles en la [decisión 018](decisiones/018-sample-sets.md).

- **Armado** (`SampleSetService.asignar_a_sample_set`, en `back/app/use_cases/sample_sets.py`): la
  llegada (T04, cuando se una) lo va a recibir con `Depends(get_sample_set_assigner)` por cada muestra recibida. Pasa la
  muestra de `received` a `in_sample_set`, la suma al lote `assembling` (o abre uno) en el siguiente
  lugar libre y, con 10 muestras o un Pompe urgente, cierra el lote y llama una sola vez a
  `al_cerrar_lote` (T06). No confirma nada: el commit lo hace la llegada.
- **Choques, sin `FOR UPDATE`**: lugar tomado → prueba el siguiente; lote lleno o cerrado por otro
  pedido → relee y, si hace falta, abre otro; lote abierto a la vez por otro pedido → usa ese. Con
  cinco relecturas seguidas falla y se deshace la llegada entera (un lugar tomado no cuenta).
- **Pompe urgente**: un estudio con la patología de código `POMPE` (sin distinguir mayúsculas) y un
  paciente menor de 4 meses **al alta del estudio** (propuesta). Sin fecha de nacimiento no es
  urgente (propuesta). Se cierra el lote armándose con lo que tenga o, si no hay, sale un lote de 1.
  `SampleSetService.es_pompe_urgente(study_id)` queda para bioinformática (sin endpoint).

| Método | Ruta | Rol | Respuesta |
| --- | --- | --- | --- |
| GET | `/api/sample-sets?status=` | `lab_administrator` | Lotes (todos sin `status`), del más nuevo al más viejo: `id`, `status`, `is_urgent`, `created_at`, `closed_at`, `sample_count` |
| GET | `/api/sample-sets/{id}` | `lab_administrator` | Lo mismo sin `sample_count` y con `samples`: `slot`, `sample_id`, `study_code`. Sin datos del paciente. 404 si no existe |

`status` es `assembling`, `closed`, `awaiting_pickup` o `in_transit_to_sequencing_lab`; otro valor
da 422. Las fechas salen en hora de Argentina.

**Pantallas** (`front/src/features/logistica/lotes/`): `/administrativo/lotes` lista los lotes por
estado (Armándose, Cerrados, Esperando retiro, En viaje), con la pestaña en la URL
(`?estado=closed`). `/administrativo/lotes/:id` muestra estado, urgencia, fechas y los lugares con
el código de estudio, y debajo el envío de T06 (`<EnvioLote session sampleSetId onChange />`, que
recarga el lote).

Pruebas: `back/tests/test_sample_sets_api.py` y `front/tests/lotes.test.mjs` (con su propio doble de
la API, `front/tests/lotes-setup.mjs`). Pompe no está en el seeder (solo carga Fabry): se prueba ahí.

## Envío internacional (T06)

Cuando el armado de lotes (T05) cierra un lote, el enganche `al_cerrar_lote` arma el CSV, pide la
autorización al Ministerio de Salud (SIMULADO) y guarda los dos archivos. Después el administrativo
programa el retiro de FedEx y consulta su estado. Detalles en la
[decisión 019](decisiones/019-envio-internacional.md).

| Método y ruta | Función |
| --- | --- |
| GET /api/shipments/{sample_set_id} | Estado del envío del lote |
| POST /api/shipments/{sample_set_id}/authorization | Reintenta la autorización del Ministerio |
| GET /api/shipments/{sample_set_id}/csv | Descarga el CSV (`lote-<id>.csv`) |
| GET /api/shipments/{sample_set_id}/authorization.pdf | Descarga el PDF (`lote-<id>-autorizacion.pdf`) |
| POST /api/shipments/{sample_set_id}/pickup | Programa el retiro. Cuerpo `{"scheduled_at": "2026-12-02T10:00:00-03:00"}` |
| POST /api/shipments/{sample_set_id}/refresh | Consulta FedEx; con `RETIRADO`, pasa el lote al viaje |

Todos son del rol `lab_administrator`. El GET y los POST responden lo mismo:

```json
{"id": 1, "status": "awaiting_pickup", "has_csv": true, "has_authorization": true,
 "pickup_at": "2026-12-02T10:00:00-03:00", "courier_pickup_id": "<uuid de FedEx>"}
```

- **CSV**: `dni,apellido,nombre,codigo_estudio,id_muestra`, una fila por muestra del lote, en el
  orden de sus lugares. Los datos del paciente salen de su repositorio.
- **Ministerio caído al cerrar**: el cierre no falla; el lote queda `closed` sin PDF y se reintenta
  con `POST .../authorization`. El PDF queda asociado a cada estudio a través de `sample_set_items`.
- **Retiro**: día hábil, desde las 9 y antes de las 18 (hora argentina), sin feriados de la tabla
  `holidays`. FedEx retira en `CENTRAL_LAB_ADDRESS`. El lote pasa a `awaiting_pickup`.
- **Consulta**: `PROGRAMADO` no cambia nada. `RETIRADO` pasa el lote y sus muestras a
  `in_transit_to_sequencing_lab` y cada estudio a `en_viaje_a_corea` (estado de Tomás, sin
  renombrar todavía). Consultar un lote ya en viaje no vuelve a llamar a FedEx ni repite nada.

Errores:

| Caso | Respuesta |
| --- | --- |
| Lote inexistente, archivo todavía no generado | 404 |
| Ya autorizado, lote armándose, retiro sin autorización, retiro ya programado, consulta sin retiro, otro pedido lo cambió antes | 409 |
| Fecha sin zona horaria, pasada, fuera de horario, fin de semana o feriado | 422 |
| El Ministerio o FedEx fallan, no se pudo guardar el CSV o el PDF, o falta `FEDEX_URL`, `FEDEX_USER` o `FEDEX_PASS` | 502 (el lote no cambia) |
| Sin token / otro rol | 401 / 403 |

Configuración: `SHIPMENT_FILES_DIR`, la carpeta del CSV y el PDF, fuera del repo. Vacío o sin
definir: `~/exoma-care-archivos`. En el lote se guarda solo el nombre del archivo.

FedEx no avisa cuando retira y no hay cron. Para la demo se consulta con el botón "Actualizar
estado" del lote o con el comando (desde `back/`):

```powershell
.\.venv\Scripts\python.exe -m scripts.consultar_retiros
```

Recorre los lotes `awaiting_pickup` y consulta cada uno. Sus eventos de muestra quedan sin usuario.

Pantalla: el bloque "Envío" del detalle del lote (`/administrativo/lotes/:id`,
`front/src/features/logistica/lotes/EnvioLote.jsx`) muestra el estado y la autorización, y deja
pedir la autorización, descargar el CSV y el PDF, programar el retiro y actualizar el estado.

Pruebas: `back/tests/test_shipments_api.py` (FedEx con un doble, archivos en una carpeta temporal)
y `front/tests/envio-lote.test.mjs`.
