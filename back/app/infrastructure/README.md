# Infraestructura

Implementaciones técnicas de los contratos usados por la aplicación: base de
datos, repositorios, seguridad y otros adaptadores. Esta capa puede depender de
bibliotecas externas; el dominio y los casos de uso no deben depender de sus
detalles.

## Carpetas

- [`database/`](./database/README.md): configuración, modelos y utilidades de
  persistencia.
- [`repositories/`](./repositories/README.md): adaptadores de repositorio
  concretos.

Los módulos directamente en esta carpeta implementan servicios técnicos
transversales, como la emisión de tokens.
