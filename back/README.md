# Backend

API de Exoma Care con Python, FastAPI y SQLAlchemy.
Los comandos siguientes son para **Git Bash**.

## Arranque diario

Desde la carpeta `back`, con el entorno y `.env` preparados:

```bash
bash dev.sh
```

Inicia Uvicorn en http://127.0.0.1:8000 con recarga al modificar código.
Documentación interactiva: http://127.0.0.1:8000/docs.
Detener con Ctrl+C. El script usa el Python de `.venv` sin activar el entorno.
También puede ejecutarse desde la raíz con `bash back/dev.sh`.

## Preparación inicial

Desde `back`:

```bash
if [ ! -f .venv/Scripts/python.exe ]; then
  python -m venv .venv
fi
./.venv/Scripts/python.exe -m pip install -r requirements.txt
if [ ! -f .env ]; then cp .env.example .env; fi
```

Completar `JWT_SECRET_KEY` en `.env` con el resultado de este comando,
ejecutado una sola vez:

```bash
./.venv/Scripts/python.exe -c 'import secrets; print(secrets.token_hex(32))'
```

Configurar `DATABASE_URL` si se requiere otra base. Luego:

```bash
./.venv/Scripts/python.exe -m alembic upgrade head
bash dev.sh
```

El `.env` real está ignorado por Git. `.env.example` es la plantilla sin
secretos. API, migraciones y cargadores leen `app/config.py`; las variables
del proceso prevalecen sobre `.env`. No se requiere `--env-file`.
El script de arranque no crea usuarios, instala dependencias ni aplica migraciones.
La carga optativa de conceptos de demostración se explica en
[el contrato del catálogo](../docs/catalogo-patologias.md).

## Pruebas

```bash
./.venv/Scripts/python.exe -m pytest -q
```

## Organización

- `app/`: API, casos de uso, dominio e infraestructura.
- `migrations/`: cambios versionados del esquema.
- `tests/`: pruebas del backend.

Entornos virtuales, archivos `.env`, bases locales y cachés no se versionan.

## Pacientes e información clínica

EC-07 requiere la migración `0003`. Desde `back`, ejecutar `./.venv/Scripts/python.exe -m alembic upgrade head` antes del arranque. El [contrato de pacientes](../docs/pacientes-clinica.md) describe permisos, endpoints y la carga opcional de cinco patologías DEMO.

## Centros de extracción y feriados

La logística requiere la migración `0004` (provincias, centros y feriados). La carga optativa y repetible de 24 provincias, 100 centros DEMO y los feriados fijos del año actual y el siguiente se corre con `./.venv/Scripts/python.exe -m app.infrastructure.database.seed_demo_extraction_centers`. Criterios en la [decisión 005](../docs/decisiones/005-logistica-turnero.md).
