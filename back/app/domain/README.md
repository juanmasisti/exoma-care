# Dominio

Núcleo del negocio: define conceptos, valores y contratos que no dependen de
FastAPI, SQLAlchemy ni otras tecnologías de infraestructura.

## Carpetas

- [`entities/`](./entities/README.md): entidades y tipos de dominio.
- `dtos/`: datos validados que cruzan los límites de los casos de uso.
- [`interfaces/`](./interfaces/README.md): protocolos/contratos que necesitan
  los casos de uso.

Las reglas de negocio deben expresarse en el dominio o en los casos de uso,
nunca acopladas a detalles de HTTP o de base de datos.
