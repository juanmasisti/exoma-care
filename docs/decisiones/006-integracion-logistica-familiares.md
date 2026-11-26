# Integración de logística y familiares: revisiones Alembic y calendario

Fecha: 02/11/2026. Develop incluye PR #4 y #5; integración en feature/informacion-familiar.

## Cadena única

La rama de familiares y la entrega de logística crearon independientemente una revisión `0004` desde `0003`. Logística ya fue integrada en develop: se conserva intacta `0004_extraction_centers.py`. La migración familiar pasa a `0005_patient_family.py`, con `revision="0005"` y `down_revision="0004"`.

Cadena vigente: `0001` usuarios/pacientes → `0002` catálogo → `0003` clínica → `0004` centros/provincias/feriados → `0005` familiares. La prueba de migraciones exige una sola cabecera y que 0004 siga correspondiendo a logística. Se registran ambos routers y ambos conjuntos de modelos; no se descarta código de ningún módulo al resolver el merge.

## Bases locales de la antigua rama familiar

Una base que ya aplicó la antigua `0004` familiar no tiene el mismo esquema que la `0004` de develop. Ejecutar upgrade o stamp sin comprobarlo es incorrecto: puede omitir logística o intentar recrear tablas familiares existentes.

Se agrega una herramienta explícita `app.infrastructure.database.reconcile_legacy_family_revision`. Por defecto solo inspecciona. Solo acepta SQLite con exactamente la antigua estructura familiar, sin ninguna tabla logística. `--apply` exige un respaldo nuevo fuera del repo. En una transacción SQLite real crea únicamente las tablas logísticas faltantes usando la revisión publicada, comprueba metadatos, referencias e integridad y recién entonces registra 0005. Ante un error se revierte la operación; no borra ni recrea pacientes, familiares o historias.

No se ejecuta durante startup. En bases nuevas, en 0003 o en la 0004 normal de logística se sigue usando `alembic upgrade head`. Si ya está en 0005 con estructura correcta, la herramienta informa que no hay cambios que hacer. Esquemas parciales o desconocidos requieren revisión manual, no se “arreglan” con un stamp.

## Calendario del PR #5

Al seleccionar de nuevo la misma fecha se limpiaban los horarios, pero `day` no cambiaba y el efecto no consultaba nuevamente. Se mantiene el comportamiento de refrescar disponibilidad y limpiar la selección de hora: cuando la fecha es la misma se incrementa explícitamente el contador de recarga. La prueba reproduce dos selecciones del mismo día, exige otra consulta y comprueba que vuelvan los horarios sin carga permanente.

Esta corrección no habilita confirmación/reserva: esa operación sigue pendiente de T02 y de su módulo económico/estudio.

## Pruebas y operación

Se prueban cadena única, base nueva, base logística 0004, base familiar antigua con datos, repetición sin cambios, rechazo de esquema parcial y rollback real de DDL ante fallo. Las pruebas completas de ambos módulos deben ejecutarse juntas antes de publicar la rama.
