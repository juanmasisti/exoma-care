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
