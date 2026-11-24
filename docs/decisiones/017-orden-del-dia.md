# Orden del día y app del transportista (T04, EC-17 parte 1)

Fecha: 24/11/2026. Área de logística (Ivo). Parte de la base de la [decisión 016](016-logistica-base.md) y
usa el cliente de recorridos de la [decisión 009](009-cliente-recorridos.md).

## Qué se hizo

- **Caso de uso** `TransportService` (`back/app/use_cases/transport.py`):
  - `generar_orden_del_dia(fecha)`: arma una orden por provincia con centros que tienen muestras
    `ready_for_pickup`. Las paradas siguen la secuencia que devuelve la API de recorridos, con partida y
    destino en el Laboratorio Central. Lo hace con `RoutePreviewService`, sin editarlo.
  - `listar`, `mi_recorrido`, `retirar` y `registrar_llegada`.
- **Repositorio de recorridos**: las lecturas de `samples` y `appointments` (centros con muestras listas y
  muestras de cada parada) están en `SQLAlchemyRouteRepository`. Los cambios de estado usan
  `SampleRepository.change_status`.
- **API** (`back/app/api/routes/transport.py`): `POST` y `GET /api/transport/daily-routes`,
  `GET /api/transport/my-route`, `POST .../stops/{stop_id}/pickup` y `POST .../arrival`. La llegada
  recibe `Depends(get_sample_set_assigner)`. Detalle en [logística](../logistica.md#orden-del-día-y-transportista-t04).
- Se borró el endpoint provisorio `POST /api/transport/route-preview`. Las pruebas del cliente de
  recorridos pasaron a `back/tests/test_transport_api.py`.
- En `front/tests/logistica-base.test.mjs` (compartido) se sacaron solo los casos "En construcción" de
  `/administrativo/ordenes-del-dia` y `/transporte`, con el OK de Ivo. Las pruebas de esas pantallas están
  en `front/tests/transportista-*.test.mjs`.
- **Pantallas**:
  - `/administrativo/ordenes-del-dia`: generar y ver las órdenes del día, con el avance de cada provincia.
  - `/transporte/*`: P1 inicio, P2 orden, P3 centro (con P4 confirmar y P5 comprobante), P6 a bordo
    (con P7 fin de recorrido, P8 confirmar y P9 llegada).
  - Usan el estilo de Consultas (`turnos-patient`) y están pensadas primero para celular. No tienen
    temperatura, incidencias, firma ni habilitación del vehículo.
  - **Rediseño con la estructura del prototipo** (rama `feature/transportista-diseno`):
    - P1 tiene indicadores, barra de avance y botón principal grande.
    - **Sin tarjeta de temperatura (2 a 8 °C).** El prototipo la tiene, pero el dominio dice que el PO
      pidió sacarla. Cuando prototipo y dominio no coinciden, manda el dominio.
    - P2 tiene una línea de paradas y un mapa (`RecorridoMap.jsx`, con leaflet como `CentersMap`) que va
      del Laboratorio Central a los centros en orden y vuelve.
    - P3 muestra una tabla con código, volumen y hora de extracción ("—" si el aviso no la trajo).
    - P4 y P8 son ventanas modales.
    - P5 y P9 son comprobantes con hora, lugar, cantidad de muestras y custodia transferida.
    - P6 muestra una tabla agrupada por centro con la hora de retiro, y P7 el balance de la jornada.
    - Para el mapa y la tabla, `my-route` suma campos sin cambiar reglas: coordenadas del centro,
      `central_lab` (de la configuración) y `samples` (código, volumen y `taken_at` del aviso). No
      incluye datos del paciente.

## Qué se decidió

- **Todas las secuencias se calculan antes de guardar.** Si la API de recorridos falla con una
  provincia, se responde 502 y no queda ninguna orden, tampoco la de una provincia de un solo centro
  (que no necesita la API).
- **Solo entran centros activos.** `RoutePreviewService` rechaza los dados de baja. Las muestras listas de
  un centro inactivo quedan afuera de la orden hasta que se reactive. Si un centro se da de baja mientras
  se genera la orden, la respuesta es 409. Esa traducción está solo en la generación: un error
  inesperado del armado de lotes en la llegada no se confunde con ese 409.
- **Fecha libre.** El contrato solo exige que sea día hábil (fin de semana o feriado: 422). Se puede
  generar la orden de otro día.
- **La llegada exige todas las paradas retiradas** (lo decidió Ivo). Con centros pendientes responde 409,
  porque el orden es fijo y no se saltea.
- **`add_route` sin savepoint.** La base guardaba la orden dentro de un savepoint. En SQLite (pysqlite)
  no se abre la transacción antes de un `SAVEPOINT`: como la primera orden es la primera escritura del
  pedido, quedaba confirmada aunque fallara la provincia siguiente (la misma falla que encontró T06 en
  el cierre de lotes). Ahora la orden es un INSERT condicional (`WHERE NOT EXISTS` por fecha y
  provincia; si no entra, `RouteAlreadyExists`) y las paradas van sin savepoint: cualquier error deshace
  el pedido entero. En SQLite el `NOT EXISTS` corre con el lock de escritura tomado, así que el índice
  único no llega a saltar. Si saltara (otro motor, por ejemplo Postgres), el pedido falla entero con 500
  y no se trata como una orden ya generada.
- **Sin `FOR UPDATE`** (SQLite).
  - El retiro y la llegada marcan la parada o la orden con un UPDATE condicional
    (`picked_up_at IS NULL`, `status = 'pending'`). De dos pedidos a la vez, uno gana y el otro recibe
    409.
  - Las muestras se cambian con `change_status`. Si cambió menos de las esperadas, responde 409 y
    deshace todo. Eso pasa antes de guardar `route_pickups`, para que un choque sea 409 y no un error
    de índice único.
- **Retiro sin muestras.** Si al llegar el centro ya no tiene muestras listas (por ejemplo, se descartó
  la única), el retiro se registra igual con 0 muestras, para poder seguir con el orden fijo.
- **La llegada recibe exactamente las retiradas**: las de `route_pickups` de la orden, no "todas las que
  estén `with_transporter`".
- **Enganche**: la llegada confirma o deshace. Si `asignar_a_sample_set` lanza, se deshace la llegada
  entera.
- **Horas en hora de Argentina** en todas las respuestas, como el resto de logística, para que el front
  las muestre sin convertir.
- **Códigos de muestra**: `study_code` del estudio (PROVISORIO, decisión abierta 4).

## Qué quedó pendiente

- **Datos del prototipo que el sistema no guarda**: patente del vehículo, temperatura de cada muestra y
  responsable del centro. Quedaron fuera del rediseño. Si el PO los pide, hay que definir dónde se
  guardan y quién los carga.
- **Rol `transporter` con provincia** (Camila, EC-03). Hoy `my-route` recibe `province_id` en el pedido y
  la pantalla lo pide en un select PROVISORIO. Las opciones salen de las órdenes de hoy
  (`GET /api/transport/daily-routes`), no de `GET /api/provinces`: ese endpoint es del turnero y solo
  acepta pacientes, y con el administrativo respondía 403. `daily_routes.transporter_id` queda nulo.
  Cuando exista el rol:
  - sacar `province_id` del pedido y tomarlo del usuario, junto con el select (`daily-routes` es solo del
    administrativo);
  - asignar el transportista al generar la orden;
  - probar el criterio de aceptación "un transportista no ve ni opera la orden de otra provincia
    (403/404)". **Hoy no se puede probar.**
- **Centro donde no se puede retirar** (por ejemplo, cerrado). El dominio deja los incidentes físicos
  fuera de alcance (secciones 1 y 6), y por eso no está "Registrar incidencias" del prototipo. Pero hoy
  un centro sin retirar bloquea la llegada. Hay que consultar con el profesor qué se hace en ese caso.
  Si hay que registrarlo, hace falta un campo nuevo, que no entra en esta tarea porque no lleva
  migraciones.
- **Una muestra en dos órdenes.** Si se generan las órdenes de dos días antes de retirar, las mismas
  muestras listas aparecen en las dos. No se rompe nada: el retiro toma lo que el centro tiene listo en
  ese momento y una muestra se retira una sola vez (`route_pickups.sample_id` único).
- **Partida del transportista**: se asume el Laboratorio Central (decisión 009, ABIERTO con el profesor).
- **Sin pruebas de las carreras.** Las ramas de 409 por carrera (UPDATE condicional que pierde,
  `change_status` que cambia menos de las esperadas) no tienen prueba: falta simular dos pedidos a la vez.
