# Simulador del bot de extracción en la app (T03d, EC-16)

Fecha: 17/11/2026. Área de logística (Ivo).

## Qué se hizo

- `POST /api/demo/extraction-notice` y `GET /api/demo/extraction-notice/studies`
  (`back/app/api/routes/demo.py`), solo para `lab_administrator`, detrás de
  `DEMO_TOOLS_ENABLED`.
- Pantalla "Simular aviso del bot" (`front/src/features/logistica/simulador/`) con su ítem en el
  menú del administrativo. Contrato en
  [logística](../logistica.md#simulador-del-bot-de-extracción-t03d).
- Sin migraciones.

## Qué se decidió

- **Se llama al caso de uso, no al webhook por HTTP.** La sección 7 del dominio dice que el
  botón de demo "hace el `POST /api/webhooks/extraction`". Acá se llama directo a
  `ExtractionService.registrar_aviso`, que es lo mismo que hace el webhook, por pedido de la
  ficha: así el secreto del bot nunca pasa por el front ni por un pedido del navegador, y el
  resultado es idéntico (una prueba compara los dos caminos con 2 ml y con 1,9 ml). El
  simulador por consola (`scripts/simular_aviso_extraccion.py`) sigue usando el webhook.
- **`external_id = sim-<uuid>` y `taken_at` = ahora** (reloj inyectable). Cada envío es un aviso
  nuevo; uno repetido para el mismo estudio da 409 por las reglas de siempre.
- **Un solo interruptor, en el back** (`DEMO_TOOLS_ENABLED`, por defecto `false`). Apagado, la
  dependencia del router responde 404 antes de pedir sesión: no se revela que existe. Sin
  variables `VITE_`.
- **El menú se entera preguntándole a la lista**: para el administrativo, `ClinicalLayout` llama a
  `GET /api/demo/extraction-notice/studies`; si responde, muestra el ítem. Se descartó un
  `/api/demo/status` aparte porque la lista ya da la misma respuesta. Se pregunta **una vez por
  sesión** (la respuesta queda guardada por `access_token`), porque cada pantalla monta su propio
  menú: si se cambia el interruptor, se ve al recargar la página o volver a iniciar sesión, y una
  falla de esa consulta deja el ítem oculto hasta entonces. Con el simulador apagado y
  la URL escrita a mano, la pantalla dice "El simulador está apagado en este servidor." sin
  "Reintentar".
- **`ClinicalLayout` importa `useSimulatorEnabled` de `features/logistica`**: es la única
  excepción, para el ítem del menú; no repetir el patrón con otros imports de features.
- **Lista de turnos reservados nueva**: no había un endpoint de turnos para el administrativo
  (la orden del día es T04). `SQLAlchemyAppointmentRepository.booked()` reutiliza la consulta de
  turnos y devuelve nombre y apellido del paciente, que el administrativo ya ve.
- **Validaciones compartidas**: `StudyCode` y `VolumeMl` salen de `routes/extraction.py` para que
  el webhook y el simulador validen igual.
- **Campo de ml con `step="any"`**: con `step="0.01"` el DOM de las pruebas (happy-dom) marcaba
  1,9 como inválido por redondeo y el formulario no se enviaba; un navegador podría hacer lo
  mismo. Los dos decimales los valida el back (422).

## Pendiente y abierto

- Cuando exista la orden del día (T04), la lista del simulador podría salir de ahí.
- Actualizar la sección 7 del dominio: el botón de demo llama al caso de uso, no al webhook.
