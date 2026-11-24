# Envío internacional: CSV, autorización del Ministerio y retiro de FedEx (T06, EC-18)

Fecha: 23/11/2026. Área de logística (Ivo).

## Qué se hizo

- **Caso de uso** `ShipmentService` (`app/use_cases/shipments.py`):
  - `al_cerrar_lote` implementa `SampleSetClosedHandler`: arma el CSV (`dni,apellido,nombre,
    codigo_estudio,id_muestra`), pide la autorización a `HealthMinistry` y guarda el CSV y el PDF;
  - `autorizar` (reintento), `programar_retiro`, `actualizar_estado`, `envio` y `archivo`.
- **Repositorio** `ShipmentRepository`: `items`, `awaiting_pickup`, `save_authorization`,
  `schedule_pickup` y `mark_in_transit`.
- **API** `/api/shipments/{sample_set_id}` (GET, `/authorization`, `/csv`, `/authorization.pdf`,
  `/pickup`, `/refresh`), todo para `lab_administrator`. `get_sample_set_closed_handler` devuelve el
  servicio, en la sesión del pedido. Se borraron `PendingSampleSetClosedHandler` y los provisorios
  `/api/shipments/pickups` de la decisión 012.
- **Configuración** `SHIPMENT_FILES_DIR` (por defecto `~/exoma-care-archivos`, fuera del repo).
- **Comando de demo** `python -m scripts.consultar_retiros`: consulta los lotes que esperan el retiro.
- **Pantalla** `EnvioLote.jsx`, dentro del detalle del lote: estado, autorización, descargas,
  programar el retiro y "Actualizar estado".

## Qué se decidió

- **Se agregó `GET /api/shipments/{id}`**, que no estaba en la ficha, y el GET y los POST responden
  el mismo esquema. Así `EnvioLote` no depende del detalle del lote de T05. Se anotó en la ficha.
- **En el lote se guarda solo el nombre del archivo** (`lote-<id>.csv`, `lote-<id>-autorizacion.pdf`),
  relativo a `SHIPMENT_FILES_DIR`. Cambiar la carpeta no rompe las rutas guardadas si se mueven los archivos.
- **Ministerio caído**: cualquier excepción del servicio externo se traduce a un error propio. En
  el cierre se loguea y no se lanza (el lote queda `closed` sin PDF). En el reintento es un 502.
  No se guarda el CSV si falla: se vuelve a armar en el reintento.
- **Cambios del lote con un UPDATE condicional**, por el estado esperado, que además sube la
  `version` del lote. Si otro pedido lo cambió antes, devuelve `False` y el caso de uso responde 409
  (o, en la consulta, no hace nada). Así consultar dos veces un retiro hecho, aunque sea a la vez,
  mueve el lote, las muestras y los estudios una sola vez. Un lote ya en viaje ni consulta a FedEx.
  `get` vuelve a leer la fila aunque la sesión ya la tenga.
- **Sin savepoint, a diferencia de `SampleSetRepository.close`.** pysqlite no abre la transacción
  antes de un `SAVEPOINT`. Si la sesión todavía no escribió nada, el savepoint confirma solo y el
  rollback del pedido no lo deshace: el enganche habría hecho commit. Se probó arreglarlo en
  `session.py` con `BEGIN` explícito, pero una lectura retiene el bloqueo hasta cerrar la
  transacción y dos pedidos concurrentes se traban ("database is locked"). Se descartó.
- **Fecha pasada = 422**, como en la decisión 012, además del horario y los feriados de la tabla.
- **Orden de los errores del retiro**: primero el estado del lote (404/409) y después la fecha (422).
  Una fecha sin zona o un cuerpo vacío los rechaza Pydantic (422) antes de todo.
- **El estado del estudio** se cambia con `StudyService` a `IN_TRANSIT_TO_KOREA` (`en_viaje_a_corea`):
  es de Tomás y no se renombró. No aparece en pantallas, errores, CSV ni PDF.
- **Eventos de muestra**: los firma el administrativo que consulta. Los del comando de demo quedan
  sin usuario.
- **Estilo**: `turnos.css` solo le da estilo al input numérico; el de fecha y hora del retiro copia
  ese estilo en línea para no tocar un archivo compartido.
- Se borró la prueba "el detalle del lote ya muestra el lugar del envío" de
  `front/tests/logistica-base.test.mjs` (T05 hace lo mismo); `EnvioLote` se prueba en
  `front/tests/envio-lote.test.mjs`.

## Qué quedó pendiente

- **Dos retiros a la vez**: si dos pedidos programan el mismo lote, los dos llaman a FedEx y uno
  responde 409. El retiro del perdedor queda sin usar en FedEx (su API no permite cancelarlo).
- **Archivos huérfanos**: si el pedido se deshace después de escribir el CSV y el PDF, quedan en la
  carpeta. Se pisan en el próximo intento con el mismo nombre.
- **`SampleSetRepository.close` (base, T05) tiene el mismo riesgo del savepoint**: si se llama antes
  de cualquier escritura de la sesión, el cierre queda confirmado aunque el pedido se deshaga. En la
  llegada real casi no pasa (T04 escribe muestras antes). Revisarlo con T05.
- **Pruebas de T05**: al cerrar lotes corren este enganche; tienen que fijar `SHIPMENT_FILES_DIR` en
  una carpeta temporal o reemplazar `get_health_ministry`, para no escribir en `~/exoma-care-archivos`.
- **Renombre de `en_viaje_a_corea`** con Tomás (ya anotado en la decisión 016).
- **Borde de las 18:00** del retiro: confirmar con el profesor (decisión 016).
- **Cambio de lote sin desmontar**: si el detalle cambia de `sampleSetId` sin desmontar `EnvioLote`, se
  ve el envío anterior hasta que llega la respuesta. Hoy no pasa (cada lote es otra ruta); si pasa, montarlo con
  `key={sampleSetId}`.
- **Sin cron**: FedEx no avisa; se consulta con el botón o el comando.
