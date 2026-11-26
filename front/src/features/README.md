# Funcionalidades

Cada subcarpeta representa una funcionalidad completa del producto asociada a
un dominio. Se esperan aquí las páginas/vistas que resuelven un flujo completo,
su navegación local, componentes específicos, estilos, tipos, hooks y pruebas.
Una feature debe poder entenderse y evolucionar con la mayor parte de su código
en un mismo lugar.

Los componentes específicos de una sola feature se quedan dentro de ella. Un
`widget` es una sección funcional concreta que puede compartirse entre páginas;
si es genérico y puramente de interfaz, corresponde a `components/`. Evitar
duplicar widgets: ubicarlos en un módulo compartido cuando haya reutilización
real.

## Funcionalidades actuales

- [`estudios/`](./estudios/README.md): ciclo de vida y consulta de estudios.
- [`logistica/`](./logistica/README.md): operaciones de logística vinculadas
  con el circuito de muestras.
- [`pacientes/`](./pacientes/README.md): gestión y vistas del paciente.

Estas carpetas son puntos de organización iniciales; agregar páginas y lógica
cuando se implemente cada funcionalidad.
