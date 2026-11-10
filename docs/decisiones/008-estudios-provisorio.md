# Estudios: tabla mínima provisoria para destrabar turnos

Fecha: 10/11/2026. Área de logística (Ivo). Avisado al equipo.

## Por qué existe

Turnos, muestras y sample sets cuelgan de un estudio, y la tabla `studies` es del área de
estudios (Tomás), que todavía no está. Para no frenar T02 se arma una versión **mínima y
provisoria**. Tomás la amplía después con su propia migración (desde `0006`); no se reemplaza.

## Qué se hizo

- Tabla `studies` (migración `0006`): `id`, `patient_id` (FK a `patients.id`), `status`, `created_at`.
  `status` es `String` y no un enum de base, para sumar estados sin migrar datos.
- Estados válidos en `app/domain/entities/study.py`, con los nombres del glosario.
- Contrato que usa logística: **solo** estas dos funciones de `StudyService` (`app/use_cases/studies.py`):
  - `estudio_habilitado(study_id) -> bool`: `True` si el estado es `pagado` o `autorizado`;
    `LookupError` si el estudio no existe.
  - `cambiar_estado_estudio(study_id, nuevo_estado) -> None`: `ValueError` si el estado no está
    en la lista; `LookupError` si el estudio no existe.
- Seed DEMO optativo y repetible `seed_demo_studies`: para el paciente con DNI 45000001 crea un
  estudio `pagado`, uno `autorizado` y uno `pendiente_pago`. Si el paciente no existe, avisa y no crea nada.
- Sin endpoints ni pantallas: se agregan en T02 cuando hagan falta.

## Ajuste en la herramienta de reconciliación de familiares (avisar a Juanma)

`reconcile_legacy_family_revision.py` (decisión 006) comparaba la base contra todo
`Base.metadata` y solo reconocía `0005` como terminado, así que con `0006` sus pruebas fallaban.
Cambio mínimo: `TABLES_AFTER_0005` (tablas que se ignoran al validar el esquema 0005) y
`REVISIONS_AFTER_0005` (revisiones que cuentan como "nada que hacer"). **Cada migración nueva
que cree tablas tiene que sumarse a esas dos constantes.**

## Qué queda para Tomás

- Tabla de transiciones permitidas y el parámetro `actor` que pide el contrato del dominio
  (`cambiar_estado_estudio(study_id, nuevo, actor)`). Hoy cualquier estado válido se acepta.
- El resto de los campos del estudio (pagos, presupuesto, autorización, médico, etc.).
- Mantener las dos funciones con la misma firma (o avisar si cambia) para no romper logística.
