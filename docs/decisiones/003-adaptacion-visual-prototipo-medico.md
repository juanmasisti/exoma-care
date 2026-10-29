# Adopción visual del prototipo del médico: cierre de EC-06

Fecha: 2026-10-28. Alcance confirmado por Juanma: cerrar EC-06 con adaptación
visual y planificar pacientes en el siguiente incremento.

## Qué se adopta

Marca con referencia a ADN, gama índigo y neutros, estructura de barra lateral,
encabezado con ubicación actual, fichas de criterios, formularios por secciones
y estados visibles de validación. El layout permite reutilizar esa estructura.
Se mantiene React/JSX, CSS, React Router y las dependencias existentes.

## Qué permanece funcional

Catálogo, edición por gerente, consulta por médico, búsqueda de conceptos y
validación individual utilizan los servicios y la persistencia de EC-06.
La búsqueda por nombre filtra únicamente las patologías ya cargadas.
No se cambia el login, la API, las reglas ni el esquema de la base.
No se muestran identidades médicas o métricas inventadas del prototipo.

La navegación contiene únicamente el módulo disponible por perfil. El catálogo
del médico sigue siendo una herramienta provisional; no representa el portal
clínico completo. No se incorporan enlaces a funcionalidades inexistentes.

## Qué no se importa del prototipo

- Autenticación simulada y estado inicial de usuario ya autenticado.
- Datos clínicos, genes o relaciones patología/síntoma sin catálogo confirmado.
- Creación de pacientes antes de validar la sospecha.
- Síntomas de texto libre ni inserción automática de relatos clínicos simulados.
- Uso de cupones al asignarlos, clasificación adicional de resultados o un
  archivo de texto presentado como PDF.
- TypeScript, Tailwind, librerías de IA o Express: no son necesarios para
  adaptar la presentación y no reemplazan FastAPI.

## Siguientes incrementos

EC-07 implementará alta, consulta y actualización de pacientes con validaciones
en backend y persistencia. Primero deben resolverse sospecha familiar sin
síntomas, validación mixta, alcance de acceso entre médicos y cuenta del paciente.
Familiares/familiograma y dictado corresponden a EC-08/09. Estudios, genes,
cupones y reanálisis requieren los contratos del área de Tomás; resultados,
los de Camila. La navegación se integrará cuando esos módulos estén disponibles.

El análisis detallado del ZIP y las notas para la defensa permanecen fuera
del repositorio. Esta decisión conserva solo el alcance compartido del equipo.
