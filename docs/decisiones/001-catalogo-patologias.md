# EC-06: catálogo de patologías y validación individual

Fecha: 2026-10-28. Responsable: Juanma.

## Base y organización

- `develop` parte de `feature/arquitecture` (b35501e), sin eliminar esa rama.
- Las nuevas funcionalidades se integrarán a develop. Main conserva su función estable.
- Se mantiene React/Vite y FastAPI/SQLAlchemy con las capas existentes.
- Cada responsable implementa BD, servicios y frontend de su dominio.

## Regla confirmada

La entrevista corregida (pp. 26-27) y los escenarios 8, 9 y 31 establecen
un síntoma cardinal o al menos dos secundarios asociados a la patología.
Se cuentan síntomas distintos: repetir el mismo código no suma evidencia.
El resultado indica coherencia de una sospecha clínica, nunca un diagnóstico.
La misma regla se usará desde el backend para evitar depender del navegador.

## Límites de esta entrega

Se implementa validación individual. No se registra un paciente ni se crea un
estudio. No se decide si un conjunto de sospechas permite confirmar el alta.
No hay integración SNOMED ni relaciones médicas inventadas. Los conceptos
de demostración son explícitamente ficticios y su carga es optativa.

## Decisiones funcionales pendientes

1. Criterio para sospecha familiar sin síntomas.
2. Comportamiento ante sospechas múltiples con resultados mixtos.
3. Catálogos oficiales y contrato del proveedor de terminología.

Estas decisiones no impiden construir el catálogo y su validador individual.
Antes del alta de pacientes deberán resolverse con el equipo.

## Aclaración documental confirmada

La referencia CCB de la transcripción es un error: el archivo para el envío
se genera en formato CSV (.csv). Esta corrección aplica al dominio compartido.

## Apoyo mínimo de acceso para esta entrega

Se conecta el login existente a la API y se agrega el código estable `role`
sin eliminar la etiqueta `rol`. Se verifica JWT y el usuario/rol actual en BD.
Esto permite probar EC-06 con gerente y médico sin autorizarlo por datos
enviados desde el navegador. La gestión completa de identidad sigue asignada
a Camila; el segundo factor y primer acceso continúan pendientes.

La sesión temporal vive en memoria. No se introducen tokens en almacenamiento
persistente del navegador. Esta decisión reversible permite integrar la
solución definitiva de Camila sin trasladar autenticación al módulo clínico.

## Integridad y migraciones

Las tablas del catálogo están separadas de usuarios y pacientes. Se versiona
primero el esquema recibido (0001) y luego el catálogo (0002), sin migración
automática al iniciar. SQLite habilita claves foráneas en cada conexión de la
aplicación. La carga DEMO es optativa y no configura patologías reales.
