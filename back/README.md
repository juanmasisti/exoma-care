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

## Base SQLite y datos DEMO

SQLite ya está configurado por defecto: desde `back`, la base local se crea
como `exoma_care.db` cuando se aplican las migraciones. No hace falta instalar
ni iniciar un servidor de base de datos. El archivo está ignorado por Git.

Con el entorno virtual y `back/.env` preparados, desde PowerShell:

```powershell
Set-Location .\back
.\.venv\Scripts\python.exe -m seeders
```

El comando aplica `alembic upgrade head` antes de cargar usuarios, catálogo
DEMO, la cuenta y ficha de paciente DEMO, logística y estudios. Crea un estudio
disponible para bioinformática y es idempotente: al repetirlo conserva datos
existentes y no duplica los datos DEMO. También puede ejecutarse un solo grupo con `python -m seeders users`,
`patients`, `catalog`, `concepts`, `logistics` o `studies`; todos aplican
primero las migraciones.

Los usuarios y catálogos son ficticios y solo sirven para desarrollo. Las
cuentas de personal DEMO usan la contraseña inicial documentada por el
seeder; el paciente DEMO recibe una contraseña aleatoria que se muestra una
sola vez cuando se crea. No usar estos datos ni credenciales en producción.

El seeder de usuarios incluye una cuenta DEMO `super_admin`. Al iniciar sesión,
el Super Admin puede usar el dashboard de [administración de usuarios](../front/src/features/admin/UsersDashboard.jsx)
para registrar médicos tratantes, administrativos del laboratorio y
bioinformáticos. El email funciona como identificador de acceso; la contraseña
temporal se muestra una sola vez al terminar el alta y debe compartirse por un
canal seguro.

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

La logística requiere la migración `0004` (provincias, centros y feriados). La carga optativa y repetible de 24 provincias, 100 centros DEMO y los feriados fijos del año actual y el siguiente se corre con `./.venv/Scripts/python.exe -m seeders logistics`. Criterios en la [decisión 005](../docs/decisiones/005-logistica-turnero.md).

## Información familiar

EC-08 agrega la migración `0005`, posterior a `0004` de logística, y la pestaña Familiares de la ficha médica. Aplicar `alembic upgrade head` desde el entorno del backend antes de iniciar. Ver [contrato familiar](../docs/informacion-familiar.md); la integración del PDF de familiograma continúa pendiente.

Si ya usaste la antigua `0004` de la rama familiar, seguí la [reconciliación explícita](../docs/informacion-familiar.md#reconciliar-una-base-local-de-la-antigua-0004-familiar) antes del upgrade normal. No basta con cambiar el nombre de una revisión ni usar stamp.

## Análisis bioinformático

Las migraciones `0007` y `0008` guardan la asignación del bioinformático y los
resultados estructurados. Apigen se configura con `APIGEN_BASE_URL` y
`APIGEN_API_KEY` en `back/.env`; también se acepta el nombre local
`API_GEN_URL` y `API_SECRET_KEY_API_GEN` para compatibilidad. La credencial de
Apigen se envía en `apikey`, nunca como Bearer ni como `JWT_SECRET_KEY` de
Exoma. Las búsquedas de listas de variantes quedan en cache local durante 10
minutos por consulta (gen, filtro y paginación), con un máximo de 256 entradas
por proceso. Este cache no incluye datos de pacientes ni resultados clínicos,
y se vacía al reiniciar el backend.

Los endpoints `/api/bioinformatica/estudios`, `/iniciar`,
`/variantes` y `/resultados` requieren exclusivamente `bioinformatician`.
La toma del análisis se realiza con actualización condicional para impedir
que dos usuarios reclamen el mismo estudio. El resultado solo puede ser
positivo si hay al menos una variante `patogenica`; ante hallazgos
`probablemente_patogenica` o `vus` sin resultado positivo, se agenda
reevaluación a 365 días. Las respuestas HTTP de error de Apigen conservan su
código; errores de red y timeout se traducen a 503.

El endpoint anterior `POST /api/estudios/{id}/analizar` se mantiene por
compatibilidad. Esta integración no implementa carga de datos crudos ni
generación/publicación de PDF.

El selector bioinformático de patologías consulta CDSS a través del backend.
Configurar `CDSS_BASE_URL` (por defecto `https://genexoma.onrender.com`) y
`CDSS_API_KEY` en `back/.env`. El endpoint
`GET /api/bioinformatica/patologias` solo admite los roles `bioinformatician`
y `super_admin`; las demás rutas bioinformáticas siguen restringidas al
bioinformático.
