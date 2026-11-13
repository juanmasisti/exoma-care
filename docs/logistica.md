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
# Debe informar 0007. Carga opcional de provincias, 100 centros DEMO y feriados fijos:
./.venv/Scripts/python.exe -m app.infrastructure.database.seed_demo_extraction_centers
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

`POST /api/transport/route-preview`. Por ahora es para el rol `lab_administrator`, hasta que
exista `transporter`. **Provisorio para la demo:** en T04 los centros salen de la orden del día.

```json
{"center_ids": [12, 3, 47]}
```

Devuelve los centros activos (con la misma forma que `GET /api/extraction-centers`) en el orden de
visita. El recorrido sale del Laboratorio Central (Calle 62 N° 555, La Plata) y vuelve a él.

| Caso | Respuesta |
| --- | --- |
| 0 o 1 centros | 200 con la misma lista, sin llamar al módulo |
| Centro inexistente o inactivo | 404 |
| Ids repetidos o más de 100 | 422 |
| El módulo falla, tarda más de 5 s o devuelve un punto que no es de ningún centro | 502 con el motivo; no se arma ningún orden |
| Sin token / otro rol | 401 / 403 |

Pruebas: `tests/test_route_preview_api.py` (doble del módulo; no salen a internet).
