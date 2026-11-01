# Logística: centros de extracción y horarios (EC-15)

Implementación y reglas: [decisión 005](decisiones/005-logistica-turnero.md).
Requiere JWT con rol `patient`. Por ahora solo consulta: las reservas llegan en una entrega posterior.

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
no tienen horarios.

Errores:
- 401: sin sesión.
- 403: rol distinto de `patient`.
- 404: centro inexistente o inactivo.
- 422: `date` ausente o inválida (enviarla como AAAA-MM-DD), o `q` de más de 100 caracteres.

## Pantalla del paciente

`/paciente/turnos/reservar` (solo rol `patient`; código en
`front/src/features/logistica/turnos/`). El paciente elige provincia, centro (en las
tarjetas o en el mapa de OpenStreetMap), día y horario libre, y ve su selección. Usa los
tres endpoints de arriba. "Confirmar turno" queda deshabilitado hasta que exista la reserva.
Detalles en la [decisión 005](decisiones/005-logistica-turnero.md#t01-pantalla-del-paciente-para-elegir-centro-y-horario).

## Preparar y ejecutar (Git Bash)

Desde `back`:

```bash
./.venv/Scripts/python.exe -m alembic upgrade head
# Debe informar 0004. Carga opcional de provincias, 100 centros DEMO y feriados fijos:
./.venv/Scripts/python.exe -m app.infrastructure.database.seed_demo_extraction_centers
bash dev.sh
```

El seed carga los feriados del año actual y del siguiente. Al empezar cada año hay que
volver a correrlo. Los feriados trasladables y los puentes se cargan a mano en `holidays`.

## Verificación

`./.venv/Scripts/python.exe -m pytest -q` desde `back`. Las pruebas de la API están en
`tests/test_extraction_centers_api.py` y fijan la hora actual reemplazando `get_clock`.

Pantalla: `npm test` y `npm run lint` desde `front` (Node `^20.19.0` o `>=22.12.0`). Las
pruebas están en `front/tests/turnos.test.mjs` y fijan la fecha con `mock.timers`.
