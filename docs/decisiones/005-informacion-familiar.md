# EC-08: información familiar del paciente

Fecha: 31/10/2026. Rama feature/informacion-familiar desde develop a3f8c48.

## Requisitos y acuerdos

Entrevista corregida pp. 8–9 y escenario 7: registrar familiares, parentesco, nombre, síntomas codificados y diagnósticos conocidos; la sección puede quedar vacía. Juanma confirmó en este incremento que los familiares son antecedentes independientes de la ficha: no crean un paciente, usuario ni vinculación automática con otra ficha. Si necesitan atención, el alta se realiza por separado.

No hay contrato disponible de la API de familiograma. Juanma confirmó completar gestión familiar y dejar PDF pendiente. No se genera un PDF local presentado como integración ni se ofrece un enlace ficticio. La respuesta informa `familiogram_status: not_configured`.

Todos los médicos tratantes pueden consultar y modificar familiares de todos los pacientes, conforme al permiso global de EC-07. Gerente, paciente y anónimo no acceden a estos endpoints.

## Decisiones técnicas del incremento

- Se agrega una familia versionada por paciente, con miembros y asociaciones a síntomas/patologías del catálogo. El parentesco se expresa respecto del paciente. No es un grafo de parentescos ni inferencia de herencia.
- Nombre y parentesco obligatorios por familiar. Parentescos iniciales del prototipo: madre, padre, hermano/a, hijo/a, tío/a, abuelo/a, primo/a; Otro exige aclaración. No se agregan edad/sexo obligatorios por no estar requeridos para esta etapa.
- Síntomas y diagnósticos opcionales. Estado diagnóstico explícito: `unknown` = sin información; `none` = sin diagnóstico conocido; `known` = diagnóstico conocido y al menos una patología del catálogo. No son un resultado negativo/positivo ni un diagnóstico calculado. Las notas permiten aclarar antecedentes.
- No aplicar el validador cardinal/dos secundarios a un diagnóstico familiar conocido. No reemplaza el antecedente documentado de sospecha familiar de EC-07 ni cambia sus reglas.
- Guardado de lista completa, atómico y con versión obligatoria. Máximo técnico de 50 familiares por ficha, 100 síntomas y 100 patologías por familiar; no son límites clínicos establecidos por el PO.
- Sin unicidad por nombre o parentesco: podrían existir dos hermanos con nombres iguales o parientes homónimos. Los IDs internos de filas no son identidad de un paciente ni un contrato de sincronización entre fichas.
- Versión e historial familiares independientes de la clínica. No se cambia `patients.version`, cuentas ni estudios. Versiones antiguas conservan nombres, códigos y etiquetas usados al guardar, aunque cambie el catálogo.
- Reemplazar/quitar familiares modifica estado actual, conserva revisiones previas. No hay purga de historial ni recuperación automática de versiones antiguas.
- Un conflicto 409 conserva el borrador. El médico debe comparar con versión guardada y decidir descartar su borrador o continuar con su lista sobre esa versión. El siguiente guardado sigue protegido frente a ediciones posteriores; no hay mezcla automática ni reintento silencioso.

## Persistencia y operación

Migración `0004`: patient_family_records, family_members, family_member_symptoms, family_member_diagnoses y patient_family_revisions. No modifica la clínica existente ni siembra familiares. La API no aplica migraciones al arrancar.

Antes de actualizar una base a conservar, respaldarla. Revertir 0004 elimina toda la información familiar y sus revisiones; no usar downgrade como forma de vaciar una ficha ni para resolver una incidencia de arranque.

## Pendientes expresos

Contrato del generador PDF, estructura de grafo/parentescos del proveedor, asociación/almacenamiento y permisos de descarga del documento; vinculación opcional futura con pacientes existentes, si el equipo la solicita. Mantener datos DEMO identificados y sustituirlos por terminología validada solo con catálogo confirmado.
