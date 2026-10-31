# Información familiar — EC-08

Reglas y decisiones: [005-informacion-familiar](decisiones/005-informacion-familiar.md).

## API

JWT con rol `treating_physician`. El permiso es global entre médicos y siempre se comprueba que el paciente exista.

| Método/ruta | Resultado |
| --- | --- |
| GET /api/patients/{id}/family | Familia vigente, versión y estado de integración del PDF |
| PUT /api/patients/{id}/family | Reemplaza la lista completa atómicamente y agrega revisión |
| GET /api/patients/{id}/family/history | Revisiones descendentes con autor y datos guardados |

Antes del primer guardado, GET devuelve `version: 0`, `members: []`, `updated_at: null`. No genera una fila por consultar. La respuesta indica `familiogram_status: not_configured`.

Ejemplo de PUT (usar IDs reales del catálogo local):

```json
{
  "version": 0,
  "members": [{
    "full_name": "Familiar ficticio",
    "relationship": "mother",
    "relationship_detail": "",
    "symptom_ids": [],
    "diagnosis_status": "unknown",
    "diagnosis_ids": [],
    "notes": "Antecedente informado, sin datos reales"
  }]
}
```

Parentescos: `mother`, `father`, `sibling`, `child`, `aunt_uncle`, `grandparent`, `cousin`, `other`. Otro exige `relationship_detail`. Nombre: 1–200 caracteres, aclaración hasta 100, notas hasta 4000. Hasta 50 miembros y hasta 100 IDs positivos por colección. Se rechazan campos ajenos y conceptos inexistentes. Se deduplican IDs, no personas por nombre.

`diagnosis_status`: `unknown` sin información; `none` sin diagnóstico conocido; `known` exige al menos un `diagnosis_id`. En unknown/none la lista diagnóstica debe estar vacía. La respuesta agrega `symptoms` y `diagnoses` con etiquetas guardadas. Esas propiedades de lectura no deben reenviarse al PUT.

Se puede guardar `members: []` para retirar todos los antecedentes actuales; se conserva el historial. Cada guardado usa la versión devuelta por GET y crea la siguiente revisión. La versión no es la de la ficha clínica.

Errores: 401 sin sesión válida; 403 rol ajeno; 404 paciente inexistente; 409 versión vieja/cambio simultáneo; 422 formulario, IDs o diagnóstico inconsistentes. Ante 409 no reenviar automáticamente con una versión nueva: comparar y decidir qué datos se quieren guardar.

## Base y arranque (Git Bash Windows)

Desde `back`, con `.env` y dependencias preparados y respaldo de la base:

```bash
./.venv/Scripts/python.exe -m alembic upgrade head
./.venv/Scripts/python.exe -m alembic current
# Debe indicar 0004
bash dev.sh
```

Desde `front`, en otra terminal: `npm run dev`. El módulo está en Médico → Pacientes → ficha → Familiares. No se necesita configurar un proveedor de PDF para usar la carga de antecedentes.

## Pruebas

Backend desde `back`: `./.venv/Scripts/python.exe -m pytest -q`.
Frontend desde `front`: `npm test`, `npm run lint`, `npm run build`.

Se verifican permisos globales entre médicos, familia vacía, guardado sin crear usuarios/pacientes, rechazo atómico, diagnóstico conocido sin exigir cardinal, diferencias unknown/none, versiones y concurrencia, snapshots estables frente a cambios de catálogo y migración sin alterar evidencia clínica anterior. La interfaz se comprueba con React/happy-dom y HTTP simulado; esto no equivale a integración real de PDF ni revisión visual completa.
