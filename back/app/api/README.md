# API

Capa de transporte HTTP. Contiene routers y dependencias de FastAPI; traduce
las solicitudes y respuestas HTTP a llamadas de casos de uso, sin implementar
reglas de negocio ni consultas de persistencia directamente.

## Carpetas

- [`routes/`](./routes/README.md): endpoints agrupados por recurso o capacidad.

`dependencies.py` reúne proveedores de dependencias (por ejemplo, sesión de
base de datos y casos de uso) que los routers pueden inyectar.
