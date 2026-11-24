# Armado automático de sample sets y Pompe urgente (T05, EC-17 parte 2 y EC-19)

Fecha: 23/11/2026. Área de logística (Ivo). Se apoya en la base de la
[decisión 016](016-logistica-base.md).

## Qué se hizo

- **Armado** (`back/app/use_cases/sample_sets.py`). `SampleSetService` implementa
  `SampleSetAssigner.asignar_a_sample_set`. `get_sample_set_assigner` (`routes/sample_sets.py`) lo arma con la
  sesión del pedido y con `get_sample_set_closed_handler` (T06). Se borró `PendingSampleSetAssigner`. Por cada
  muestra recibida:
  1. la pasa de `received` a `in_sample_set` con `change_status`;
  2. la suma al lote `assembling` (o abre uno) en el siguiente lugar libre;
  3. con 10 muestras o un Pompe urgente, cierra el lote y llama a `al_cerrar_lote`.
- **Pompe urgente**: `SampleSetService.es_pompe_urgente(study_id)`, también para bioinformática (Camila), sin
  endpoint. Usa `is_urgent_pompe` de la base.
- **Consulta** para el administrativo: `GET /api/sample-sets?status=` y `GET /api/sample-sets/{id}`
  ([logística](../logistica.md#sample-sets-t05)).
- **Repositorio**: `SampleSetRepository` suma `list_by_status`, `study_for_sample` y `pompe_inputs`; `get` suma
  el `study_id` de cada muestra.
- **Pantallas**: `/administrativo/lotes` (por estado) y `/administrativo/lotes/:id` (detalle con muestras y el
  envío de T06 debajo).

## Qué se decidió

- **Fecha de referencia de "menor de 4 meses" (decisión abierta 5): el alta del estudio**
  (`studies.created_at`, en hora de Argentina). Es fija, siempre existe y da lo mismo en el armado que cuando
  bioinformática pregunta después. Si el estudio se pidió cuando el bebé tenía 3 meses, sigue urgente aunque la muestra
  llegue más tarde. Está en una sola función, `pompe_reference_date`, y no en una constante como dice la ficha porque la fecha
  depende de cada estudio: si el profesor elige otra fecha
  (extracción o cierre del lote), se cambia ahí. **Propuesta pendiente de confirmar con el profesor.**
- **Paciente sin fecha de nacimiento: no es urgente.** No se puede calcular la edad y el lote espera a llegar a
  10, como cualquier otro. **Propuesta pendiente de confirmar.**
- **Fecha de nacimiento de `patients.fecha_nacimiento`.** La ficha dice `date_of_birth`, pero esa columna es de
  `users`. La de `patients` es la que carga el médico.
- **Lecturas provisorias.** `pompe_inputs` lee `studies`, `study_pathologies` y `patients` desde
  `SQLAlchemySampleSetRepository`, solo lectura, como las lecturas de turnos (decisión 005). Se reemplazan cuando
  estudios (Tomás) y pacientes (Juanma) ofrezcan esos datos.
- **Choques sin `FOR UPDATE`**, con las restricciones que dejó la base:
  - lugar tomado (`SlotTaken`): se prueba el siguiente;
  - lote lleno (`SetFull`) o cerrado por otro pedido (`SetNotAssembling`): se relee y, si no hay lote armándose,
    se abre otro;
  - lote abierto a la vez por otro pedido (`AssemblingSetExists`): se relee y se usa ese;
  - con cinco relecturas seguidas (`MAX_ATTEMPTS`: lote abierto, lleno o cerrado por otro pedido) falla con
    `RuntimeError` y se deshace la llegada entera. Un lugar tomado no cuenta como intento.
- **El aviso de cierre lo da quien gana el cierre.** `close` es condicional: si otro pedido ya cerró el lote,
  devuelve `False` y no se vuelve a avisar. Así `al_cerrar_lote` se llama una sola vez por lote.
- **Errores del armado.** Una muestra que no está `received` da `ValueError`; una muestra o estudio inexistente
  da `LookupError`; una hora sin zona da `ValueError`; una muestra que ya está en un lote da `SampleAlreadyInSet` (no debería
  pasar: `change_status` solo la mueve desde `received`). Todos deshacen la llegada, como pide el contrato.
- **El detalle no muestra datos del paciente**, solo el código del estudio (`study_code`). Las fechas salen en
  hora de Argentina, como el resto de logística.
- **Pruebas de choque en la misma sesión.** SQLite tiene un solo escritor y la llegada ya tiene el lock (movió
  la muestra) cuando lee el lote: el otro pedido se simula entre la lectura y el alta, con repositorios que
  heredan del real.
- **Pruebas del front con doble propio** (`front/tests/lotes-setup.mjs`), para no tocar `turnos-setup.mjs`. Ivo
  autorizó este archivo y el cambio en `logistica-base.test.mjs`, que no estaban entre los propios de la ficha. De
  `logistica-base.test.mjs` se sacaron las filas de lotes (pasaron a `lotes.test.mjs`) y la prueba del envío:
  `EnvioLote` es de T06 y las pruebas de lotes no miran su contenido.

## Qué quedó pendiente

- **Confirmar con el profesor**: la fecha de referencia (alta del estudio), el paciente sin fecha de nacimiento
  (no urgente) y el lote de 1 por Pompe urgente sin lote armándose (decisión abierta 6, ya en
  `sample_set_must_close`).
- **Un lote `assembling` con 10 muestras traba el armado.** La 10.ª alta y el cierre van en la misma
  transacción, así que con este código no pasa. Pero si datos viejos o una carga manual lo dejaran así, cada
  llegada choca cinco veces y falla. Si pasa, hay que cerrarlo a mano.
- **La llegada (T04)** todavía no existe en esta rama: hasta que se una, el armado solo corre en las pruebas.
- **Probar `onChange` del envío.** El detalle recarga el lote cuando `EnvioLote` llama a `onChange` y, si la
  recarga falla, muestra el error sin borrar el lote ni desmontar el envío. Las pruebas de lotes no lo ejercen
  porque no miran `EnvioLote`: lo prueba T06 cuando lo implemente.
- **Pompe no está en el seeder** (solo carga Fabry): se prueba en `back/tests/test_sample_sets_api.py`.
- **Solo SQLite**, como dice la decisión 016.
