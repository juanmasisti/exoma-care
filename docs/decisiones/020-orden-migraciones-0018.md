# Orden de las migraciones 0018 (logística y reanálisis)

Fecha: 24/11/2026. Área de logística (Ivo), a confirmar con Tomás (reanálisis) y Juanma (migraciones).

Los números 017 a 019 están reservados para T04 a T06 (decisión 016), por eso esta es la 020.

## Problema

Al mergear el PR #23 quedaron dos migraciones con el mismo id de revisión, `"0018"`, y las dos
con `down_revision = "0017"`:

- `0018_transport_sample_sets.py` (logística, PR #22);
- `0018_study_reanalysis.py` (reanálisis de estudios, PR #23).

Alembic avisa `Revision 0018 is present more than once` y `alembic heads` muestra dos cabezas. Con
esto fallan `alembic upgrade head`, los seeders y 10 pruebas (más 11 errores) en `develop`. No se puede
resolver con una migración de merge: las dos tienen el mismo id y `alembic merge heads` responde
`Duplicate head revisions specified`.

## Qué se hizo

- El reanálisis pasa a `0019_study_reanalysis.py`, con `revision = "0019"` y `down_revision = "0018"`
  (después de logística, que se mergeó primero). El contenido de la migración no cambia.
- Se agregó `"0019"` a `REVISIONS_AFTER_0005` en `reconcile_legacy_family_revision.py`. No va en
  `TABLES_AFTER_0005`, porque el reanálisis no crea tablas: solo agrega columnas a `studies` y a
  `study_budgets`.
- `test_migrations.py` espera la cabeza `0019` y verifica que `0019` venga de `0018`.
  `test_reconcile_clinical_revision.py` espera `0019` después de `upgrade head`.

## Cómo acomodar una base local existente

Primero hay que saber cuál de las dos `0018` tiene aplicada la base. Desde `back/`:

```powershell
.\.venv\Scripts\python.exe -c 'import sqlite3; c=sqlite3.connect("exoma_care.db"); cols=[r[1] for r in c.execute("PRAGMA table_info(studies)")]; t=c.execute("select count(*) from sqlite_master where name=''daily_routes''").fetchone()[0]; print("version", c.execute("select version_num from alembic_version").fetchone()[0], "| reanalisis:", "original_study_id" in cols, "| logistica:", bool(t))'
```

### Base con logística como 0018 (`logistica: True`)

No hace falta nada especial: `.\.venv\Scripts\python.exe -m alembic upgrade head` aplica la `0019`
(reanálisis) y conserva los datos.

### Base con reanálisis como 0018 (`reanalisis: True`, `logistica: False`)

Si se corre `upgrade head` directamente, Alembic cree que la `0018` aplicada es la de logística, intenta
aplicar el reanálisis otra vez y falla con `index ix_studies_original_study_id already exists`. Además,
las tablas de logística no se crean nunca. Si ya lo corriste, volvé a la copia del paso 1.

Desde `back/`, con el back apagado:

```powershell
# 1. Copia de seguridad
Copy-Item exoma_care.db exoma_care.antes-0019.db
# 2. Marcar la base en 0017 sin tocar el esquema (el reanálisis queda aplicado)
.\.venv\Scripts\python.exe -m alembic stamp --purge 0017
# 3. Aplicar solo la 0018 de logística (crea sus tablas; no toca studies ni study_budgets)
.\.venv\Scripts\python.exe -m alembic upgrade 0018
# 4. Marcar el reanálisis como aplicado, porque sus columnas ya están
.\.venv\Scripts\python.exe -m alembic stamp 0019
# 5. Comprobar: tiene que decir "0019 (head)"
.\.venv\Scripts\python.exe -m alembic current
```

Si algo falla, restaurá con `Copy-Item exoma_care.antes-0019.db exoma_care.db -Force`.

### Prueba de los pasos

Se probaron en copias descartables:

- Base armada con `origin/feature/reanalisis-estudios`: migrada y con seeders, un estudio con
  `original_study_id` y un presupuesto con `discount_cents`.
  - `upgrade head` directo falla como se describe arriba.
  - Con los pasos 1 a 5 la base queda en `0019`, conserva el estudio y el descuento, tiene las cinco
    tablas de logística y su esquema no tiene diferencias con los modelos (`compare_metadata`).
- Base con logística como `0018` y datos: `upgrade head` la deja en `0019` con los datos y sin
  diferencias con los modelos.

## Pendiente

- OK de Tomás antes de mergear, porque la migración es suya.
- Avisar a Juanma por el cambio en reconcile.
- Avisar al equipo que quien tenga el reanálisis aplicado siga los pasos de arriba.
