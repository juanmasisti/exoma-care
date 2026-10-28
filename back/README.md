# Backend

API de Exoma Care desarrollada con FastAPI, SQLAlchemy y Python. La aplicación
se ejecuta desde esta carpeta con `uvicorn app.main:app`; la configuración
local, como `JWT_SECRET_KEY`, se proporciona mediante variables de entorno y
nunca se guarda en el repositorio. Las dependencias están declaradas en
`requirements.txt`.

## Carpetas

- [`app/`](./app/README.md): aplicación y código de producción, separado por
  capas.
- [`tests/`](./tests/README.md): pruebas automatizadas del backend.

El entorno virtual, las cachés, bases de datos locales y otros archivos
generados son artefactos de desarrollo, no código fuente.


## Configuración local

Copiar `.env.example` como `.env` y completar `JWT_SECRET_KEY` con un secreto
aleatorio de al menos 32 bytes. `DATABASE_URL` permite elegir la base local.
El archivo real está ignorado por Git; la plantilla no contiene secretos.
API, Alembic y cargadores usan `app/config.py`, basado en pydantic-settings.
Las variables del proceso prevalecen sobre `.env`. No hace falta pasar
`--env-file` a Uvicorn. Reiniciar el backend después de cambiar configuración.

Desde `back`: aplicar `python -m alembic upgrade head` y ejecutar
`python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000`.
