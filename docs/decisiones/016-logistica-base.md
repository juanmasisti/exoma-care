# Base común de transporte, lotes y envío (T04-base, EC-17 a EC-19)

Fecha: 23/11/2026. Área de logística (Ivo).

T04 (orden del día y transportista), T05 (sample sets y Pompe) y T06 (CSV, autorización y FedEx)
se van a hacer en paralelo. Esta base deja hecho todo lo que las tres comparten, así cada una toca
solo sus propios archivos. Las decisiones de cada tarea quedan reservadas: 017 (T04), 018 (T05) y
019 (T06).

## Qué se hizo

- **Dominio** (`logistics.py`):
  - estados de recorrido (`pending` → `arrived`) y de lote (`assembling` → `closed` →
    `awaiting_pickup` → `in_transit_to_sequencing_lab`);
  - reglas puras: `next_stop_sequence`, `sample_set_must_close`, `is_urgent_pompe` e
    `is_valid_pickup_time`.
- **Migración 0018**, con las tablas `daily_routes`, `route_stops`, `route_pickups`, `sample_sets` y
  `sample_set_items`, y el renombre de datos del estado en viaje. Se sumó a
  `reconcile_legacy_family_revision.py` (`TABLES_AFTER_0005`, `REVISIONS_AFTER_0005`).
- **Repositorios**: `SampleRepository.change_status` (compartido) y uno propio por tarea:
  `RouteRepository`, `SampleSetRepository` y `ShipmentRepository`, con sus SQLAlchemy.
- **Enganches** en `domain/interfaces/sample_set_hooks.py` (`SampleSetAssigner` y
  `SampleSetClosedHandler`), con implementaciones vacías junto al router de quien las implementa:
  `get_sample_set_assigner` en `routes/sample_sets.py` (T05) y `get_sample_set_closed_handler` en
  `routes/shipments.py` (T06). `api/logistics_dependencies.py` solo tiene los roles.
- **Esqueleto**:
  - router `/api/sample-sets` vacío y registrado;
  - pantallas "En construcción" con sus rutas e ítems de menú;
  - `EnvioLote.jsx`, vacío, ya dentro del detalle del lote.
- **Seeder** con muestras DEMO en cada estado
  ([logística](../logistica.md#base-de-transporte-lotes-y-envío-t04-base)).

## Qué se decidió

- **Sin "Corea" en estados, pantallas, errores, PDF ni CSV.** El estado de muestra
  `in_transit_to_korea` pasó a ser `in_transit_to_sequencing_lab`. La 0018 migra `samples.status` y
  `sample_events` y el downgrade lo revierte. La etapa del seguimiento `to_korea` pasó a ser
  `to_sequencing_lab`. En los documentos internos "Corea" puede quedar como contexto.
- **Estado de vuelta, sin definir.** Va a haber un estado intermedio cuando el resultado vuelva del
  laboratorio de secuenciación. Las transiciones son diccionarios: agregarlo es sumar el estado al
  enum y una entrada al diccionario.
- **Un repositorio por tarea y uno solo compartido.** `change_status` es un UPDATE condicional por
  muestra que deja un evento. Lo usan las tres tareas y nadie más toca `sample_repository.py`.
- **Savepoints.** Los repositorios nuevos traducen `IntegrityError` dentro de `begin_nested()`. Así,
  un choque (lugar tomado, lote ya armándose, orden ya generada) deshace solo eso y no las muestras
  recibidas del mismo pedido.
- **Errores de los lotes.**
  - `add_item` distingue cuatro casos: `SlotTaken` (otro ganó el lugar), `SampleAlreadyInSet`,
    `SetFull` (lugar fuera de 1 a 10: hay que abrir otro lote) y `SetNotAssembling`. Cualquier otro
    error se relanza.
  - `add_item` es un INSERT ... SELECT que solo entra si el lote sigue `assembling` al escribir. Así,
    un cierre que ganó antes (un Pompe urgente) no deja sumar muestras a un lote cerrado, aunque la
    llegada lo haya leído armándose.
  - `close` usa la `version` del lote: si otro pedido lo cambió, devuelve `False` y la sesión sigue
    usable.
- **Un solo lote armándose**, con un índice único parcial: si dos llegadas abren uno a la vez, una
  falla y reintenta.
- **`courier_pickup_id` en lugar de `courier_status_url`.** `Courier.estado_retiro` consulta por el
  UUID, y la decisión 012 ya admitía guardar el UUID. La sección 3 del dominio se actualizó.
- **El envío vive en el lote.** No hay tabla de envíos porque cada lote es un paquete de FedEx.
- **Pompe por código de catálogo.** `is_urgent_pompe` compara `study_pathologies.code` con `POMPE`,
  sin distinguir mayúsculas porque el catálogo DEMO usa minúsculas. Nunca compara el nombre.
- **Retiro de FedEx de 9 a antes de las 18**, igual que los turnos: las 18:00 justas no entran. El
  dominio dice "9 a 18" y no aclara el borde (ver pendientes).
- **Contrato de los enganches** (lo usan T04, T05 y T06):
  - todo corre en la sesión del pedido: se inyectan con `Depends`, y `get_database_session` es la
    misma en todo el pedido;
  - los enganches no hacen commit ni rollback: los hace quien atiende el pedido (la llegada, en T04);
  - `al_cerrar_lote` no lanza si el Ministerio falla: deja el lote `closed` sin PDF y se reintenta
    después;
  - un error inesperado del armado de lotes deshace la llegada entera.
- **Seeder idempotente por grupo**, según el id de sus avisos (`seed-logistica-<grupo>-<n>`), y no
  contando por estado como decía el plan. Así no vuelve a crear muestras cuando T04, T05 o T06 las
  avanzan. Un grupo cargado a medias se avisa y no se completa.
- Se tocó `reconcile_legacy_bioinformatics_revision.py`, que no es de logística: excluye
  `TRANSPORT_TABLES`, porque esas tablas dependen de `samples`, que la base legacy 0011 no tiene.
  También se actualizó a 0018 la cabeza fija en `test_reconcile_clinical_revision.py`.

## Qué quedó pendiente

- **Rol `transporter` (Camila, EC-03).** Hoy `TRANSPORT_ROLES` es el administrativo: es una
  constante en el back (`logistics_dependencies.py`) y otra en el front (`roles.js`), y reemplaza a
  la provisoria de la decisión 009. Cuando exista el rol:
  - cambiar las dos constantes;
  - hacer obligatorio `daily_routes.transporter_id` y asignar la orden según la provincia del
    transportista;
  - probar el criterio de T04 "otra provincia → 403/404";
  - sacar "PROVISORIO" del ítem del menú;
  - en `ClinicalLayout`, darle al rol su etiqueta, su inicio y su menú. Hoy un rol desconocido cae
    en los del médico.
- **Lote de 1 por Pompe urgente**: `sample_set_must_close` cierra con una sola muestra urgente.
  Es una propuesta pendiente de confirmar con el profesor (decisión abierta 6).
- **Fecha de referencia para "menor de 4 meses"** (decisión abierta 5): la elige T05, como una
  constante de su caso de uso.
- **Borde de las 18:00 en el retiro de FedEx**: confirmar con el profesor si entra.
- **Solo SQLite.** El INSERT condicional de `add_item` alcanza porque SQLite escribe de a uno. En
  Postgres (READ COMMITTED), un cierre sin confirmar no frena el alta. Si se cambia de motor, el alta
  tiene que bloquear la fila del lote, por ejemplo subiendo su `version` en el mismo savepoint.
- **`en_viaje_a_corea`**, el estado del estudio, es de Tomás y no se tocó. Hay que coordinar con él
  el renombre.
- El seeder no guarda recorridos ni retiros, y las muestras `received` no tienen un `route_pickups`
  detrás.
