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
- `external_services/`: clientes para APIs externas, incluido el cliente TTPS
  de notificaciones.

`notification_logs` conserva la referencia, la clave de idempotencia y el
estado inicial que devuelve el proveedor para auditar cada aviso.
