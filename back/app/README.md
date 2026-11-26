# Aplicación backend

Paquete principal de la API. Aquí viven el punto de entrada y los módulos que
implementan el dominio, los casos de uso, la infraestructura y los endpoints.
Mantener cada responsabilidad en su capa correspondiente y evitar que el
dominio dependa de FastAPI o SQLAlchemy.

## Carpetas

- [`api/`](./api/README.md): endpoints HTTP y composición de dependencias.
- [`domain/`](./domain/README.md): conceptos y contratos independientes del
  framework y la persistencia.
- [`infrastructure/`](./infrastructure/README.md): implementaciones concretas
  de persistencia y seguridad.
- [`use_cases/`](./use_cases/README.md): operaciones de aplicación y reglas de
  coordinación del negocio.

`main.py` configura FastAPI y registra los routers. Los `__init__.py` hacen
explícitos los paquetes Python.
