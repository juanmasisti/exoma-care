# EC-07: pacientes e información clínica

Fecha: 2026-10-29. Rama: feature/pacientes-clinica, iniciada desde develop.

## Reglas confirmadas por Juanma

- Todos los médicos tratantes pueden consultar y actualizar todos los pacientes del sistema. El creador no limita el acceso. Gerente y paciente no acceden a estos endpoints clínicos.
- El alta clínica se separa de la habilitación de acceso. `patients.usuario_id` admite NULL; no se crean usuarios, contraseñas ni invitaciones en este módulo. Integración de identidad pendiente con Camila.
- Sospecha clínica: cada patología seleccionada debe cumplir cardinal presente o al menos dos secundarios propios distintos, según EC-06. Si una falla, se rechaza toda la operación.
- Sospecha familiar: exige antecedente familiar documentado; permite ausencia de síntomas. No afirma diagnóstico ni exige todavía familiograma.
- Las dos reglas anteriores son provisionales y fueron confirmadas para este incremento; pueden revisarse con el equipo.

## Persistencia e historial

Se amplía `patients`, se agregan `patient_pathologies`, `patient_symptoms` y `patient_clinical_revisions`. Se conserva el creador y se registra el autor de cada revisión. Datos, asociaciones y revisión se guardan en una transacción.

Cada revisión conserva los datos personales/clínicos, conceptos seleccionados y definición del catálogo usada al validar. Cambiar el catálogo no reinterpreta el historial. Guardar una edición vuelve a validar con el catálogo vigente.

`version` evita sobrescribir una edición ajena: el cliente debe enviar la versión leída; si quedó vieja, recibe 409 y conserva su formulario. No hay eliminación de pacientes en este incremento.

El DNI se almacena sin puntos ni espacios, es único y acepta entre 1 y 20 dígitos como validación técnica básica. Email de contacto separado del email de login: puede compartirse entre pacientes, por ejemplo con un responsable. No se inventan datos clínicos ni médico creador para registros heredados.

## Cinco patologías de demostración

Se incorporan Fabry, Pompe, Mucopolisacaridosis tipo I, Gaucher y ASMD. Las asociaciones de síntomas provienen del prototipo y se identifican como DEMO. No constituyen un catálogo SNOMED ni criterios clínicos verificados. El cargador es optativo y repetible: agrega faltantes, conserva ediciones y no elimina datos previos.

## Alcance y límites

Incluye listado con búsqueda/paginación, alta, ficha, edición, validación y consulta de versiones, con navegación para médico basada en el prototipo. No crea estudios, asigna cupones ni habilita cuentas. Familiograma, dictado y circuitos de estudios siguen en sus incrementos respectivos. La consulta global corresponde a la regla funcional confirmada para esta entrega académica.
