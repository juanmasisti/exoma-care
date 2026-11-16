# Seguimiento del estudio para el paciente (T03b, EC-16)

Fecha: 16/11/2026. Área de logística (Ivo).

## Qué se hizo

- `GET /api/studies/tracking/mine` y `stage` en `GET /api/studies/{id}/tracking`. Contrato en
  [logística](../logistica.md#seguimiento-del-paciente-t03b).
- Pantalla "Seguimiento" (`front/src/features/logistica/turnos/Seguimiento.jsx`, textos en
  `etapas.js`), con enlaces desde "Mis turnos" y "Día de extracción".

## Qué se decidió

- **Endpoint nuevo para llegar al seguimiento.** Después del aviso de extracción el turno queda
  `attended` y "Mis turnos" solo lista turnos reservados: sin `/tracking/mine`, el paciente no
  tendría por dónde entrar en remuestreo o con la muestra lista. Devuelve solo estudios propios
  con al menos una muestra.
- **La etapa la calcula el back** (`tracking_stage`). Así el front no repite estados de
  bioinformática a mano: salen de `BIOINFORMATICS_STATUSES` (dominio) y
  `RESULT_AVAILABLE_STATUS` (`use_cases/bioinformatics.py`). El estado del estudio manda en
  resultado, análisis y remuestreo; en lo demás, la muestra vigente. `received` e `in_sample_set` son la misma etapa para
  el paciente.
- **Motivo del remuestreo**: el `reason` del último descarte (lo carga bioinformática con
  `solicitar_remuestreo`); si la muestra nació descartada, se explica por el volumen mínimo.
- **"Sacar turno nuevo"** usa la reserva existente con `?estudio=ID`, que ya deja ese estudio
  elegido. Solo se sumó la etiqueta "Requiere nueva extracción" a la lista de estudios de la
  reserva.
- **"Mis turnos" carga turnos y seguimiento por separado**: si falla el seguimiento, la
  lista de turnos, que es lo principal de la pantalla, se sigue viendo.
- Las etapas hechas y por venir llevan un texto oculto para lector de pantalla (no solo color).
- Sin fechas estimadas ni "resultado estimado" del prototipo (el dominio los marca como
  inventados).

## Pendiente y abierto

- Lectura PROVISORIA de `studies` y `patients` para la lista del paciente, como en turnos
  (decisión 005), hasta que estudios (Tomás) ofrezca la lista de estudios del paciente. No se
  tocó la tabla `studies`.
- El aviso por mail del remuestreo sigue en el log (T03c, con el servicio de avisos de Camila).
