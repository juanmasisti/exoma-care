# Componentes compartidos

Piezas de interfaz genéricas, reutilizables y sin pertenencia a una única
funcionalidad de negocio, por ejemplo botones, campos, modales y estructuras de
presentación. Se esperan componentes React y, cuando corresponda, sus estilos
y pruebas.

Un componente usado solo por una feature debe quedar dentro de esa feature. Una
pieza visual más específica que encapsula una sección funcional compartible
entre páginas puede organizarse como `widget` dentro de la feature o en un
directorio compartido si realmente se reutiliza.
