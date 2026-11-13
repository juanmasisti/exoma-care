# Clientes del envío a Corea: FedEx y Ministerio simulado (T06a)

Fecha: 13/11/2026. Área de logística (Ivo).

## Por qué existe

El envío del lote a Corea (T06, EC-18) necesita dos servicios externos: la API de FedEx
(módulo 10, de otro grupo) para programar el retiro y el permiso del Ministerio de Salud, que
ningún grupo implementa. Antes de T06 se dejan listos y probados los dos clientes, con un
endpoint mínimo para mostrar FedEx en la demo. No hay tablas ni migraciones.

## Contrato de FedEx (presentación del grupo)

- URL base en `FEDEX_URL`; Basic Auth con el usuario y la contraseña del grupo (`FEDEX_USER`,
  `FEDEX_PASS`, solo en `.env`).
- `POST /retiros` con `{"lugar", "fecha_programada"}`; la fecha va en hora argentina **sin
  sufijo de zona** (`YYYY-MM-DDTHH:mm:ss`). Responde 201 con `retiro.id` (UUID) y `retiro.url_seguimiento`.
- `GET /retiros/{uuid}` (público, sin auth) → `estado` `PROGRAMADO` o `RETIRADO`. FedEx lo
  calcula en cada consulta y no avisa: lo consultamos nosotros.
- Errores `{"error": "..."}`: 400 (datos inválidos o fecha pasada), 401, 404 y 500.

## Qué se hizo

- `Courier` (Protocol), `PickupStatus` y `CourierError` en `app/domain/interfaces/courier.py`.
- `HealthMinistry` (Protocol) y `MinistryAuthorization` en `app/domain/interfaces/health_ministry.py`.
- `FedExClient` (`app/infrastructure/adapters/fedex_client.py`), con `httpx` y un timeout de 5 s
  como el cliente de recorridos:
  - Convierte la fecha con `logistics.TIMEZONE` y rechaza una fecha sin zona.
  - Un estado desconocido es un error.
  - 400/401/404/5xx, timeout, falta de conexión o respuesta mal formada → `CourierError` en
    español (con el `error` de FedEx si viene). La contraseña nunca aparece en un mensaje.
- `SimulatedHealthMinistry` (`app/infrastructure/adapters/simulated_health_ministry.py`),
  **SIMULADO**: recibe el CSV y siempre devuelve "autorizado" con un PDF mínimo (`fpdf2`, una
  línea por fila). Arma su propio PDF para no depender de los documentos del turno. Solo el caso de éxito.
- Configuración: `FEDEX_URL`, `FEDEX_USER`, `FEDEX_PASS` (`SecretStr`) y `CENTRAL_LAB_ADDRESS`.
  Si falta algún dato de FedEx, la API responde 502 "FedEx no está configurado.".
- Endpoints provisorios `POST /api/shipments/pickups` y `GET /api/shipments/pickups/{id}`
  (ver `docs/logistica.md`).

## Decisiones

- **Fecha pasada = error nuestro (422)**, validado antes de llamar a FedEx con el reloj
  inyectable `get_clock`. El resto de los errores de FedEx son de un servicio externo → **502**.
- **El horario de 9 a 18 en día hábil no se valida acá**: es regla del lote y entra en T06.
- **Ministerio:** el dominio dice que devuelve "autorizado" y un PDF. Se deja así, con el PDF mínimo.
- **Endpoints provisorios sin caso de uso**: solo pasarían los datos de una capa a otra. La
  lógica del lote (autorización, `awaiting_pickup`, guardar el UUID del retiro) va en T06.
- **Rol `lab_administrator`**: el administrativo es quien programa el retiro.

## Pendiente (T06)

- Guardar el UUID (o `url_seguimiento`) del retiro en el lote y pasar a "en viaje a Corea"
  cuando FedEx diga `RETIRADO`.
- Generar el CSV del lote y llamar a `SimulatedHealthMinistry` detrás de `HealthMinistry`.
- Quitar o reemplazar los endpoints provisorios de `app/api/routes/shipments.py`.

## Pruebas

`tests/test_shipment_clients.py`:
- API con un doble de `Courier` y un reloj fijo: 201, estado, 502, fecha pasada sin llamada,
  sin zona, UUID inválido, falta de configuración, 401 y 403.
- Adaptador con `httpx.MockTransport`: hora argentina sin zona, Basic Auth solo en el POST,
  estados, estado desconocido, 400/401/404/500, JSON mal formado, timeout y falta de conexión.
- El Ministerio simulado devuelve "autorizado" y un PDF.

Ninguna prueba sale a internet.
