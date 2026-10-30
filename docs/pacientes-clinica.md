# Pacientes e información clínica: EC-07

Implementación y reglas: [decisión 004](decisiones/004-pacientes-clinica.md).
Requiere JWT con rol `treating_physician`. Todos los médicos consultan/editan todos los pacientes.

| Método y ruta | Función |
| --- | --- |
| GET /api/patients?q=&limit=20&offset=0 | Búsqueda por nombre, apellido o DNI; paginación |
| POST /api/patients/validate | Comprueba el formulario sin guardar |
| POST /api/patients | Alta clínica, devuelve 201 |
| GET /api/patients/{id} | Ficha actual y evidencia de la revisión |
| PUT /api/patients/{id} | Reemplaza ficha completa y exige `version` |
| GET /api/patients/{id}/history | Revisiones, autor y evidencia guardada |

Formulario: `dni`, `first_name`, `last_name`, `birth_date` (AAAA-MM-DD), `phone`, `email`, `clinical_summary`, `suspicion_type` (`clinical` o `family`), `family_history`, `pathology_ids` y `symptom_ids`. Los IDs deben existir en el catálogo. No acepta campos adicionales. Ver esquemas y ejemplos interactivos en `/docs` del backend.

Errores: 401 sin sesión, 403 rol no autorizado, 404 paciente inexistente, 409 DNI duplicado o versión antigua, 422 datos o criterios inválidos. La validación devuelve un resultado por sospecha; guardar exige que todos sean válidos. La operación no genera un estudio ni credenciales.

## Preparar y ejecutar (Git Bash)

Con entorno y `back/.env` preparados, desde `back`:

```bash
./.venv/Scripts/python.exe -m alembic upgrade head
./.venv/Scripts/python.exe -m alembic current
# Debe informar 0003. Carga opcional de las cinco patologías DEMO:
./.venv/Scripts/python.exe -m app.infrastructure.database.seed_demo_pathologies
bash dev.sh
```

El cargador no crea usuarios. Las instrucciones generales están en el README del backend. Antes de migrar una base con información que se quiera conservar, realizar un respaldo. El downgrade a 0002 se detiene si existen pacientes sin cuenta, para evitar imponer cuentas ficticias.

En otra terminal, desde `front`: `npm install` la primera vez y `npm run dev` para iniciar. Ingresar como médico abre `/medico/pacientes`; el catálogo sigue disponible en la navegación. Gerente conserva su módulo de catálogo.

## Verificación

Backend: `./.venv/Scripts/python.exe -m pytest -q` desde `back`.
Frontend: `npm test`, `npm run lint` y `npm run build` desde `front`.
Los tests usan datos ficticios y bases temporales; no requieren cargar pacientes en la base local.
