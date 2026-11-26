# DEC-007 — Dictado revisable del resumen clínico (EC-09)

Fecha: 2026-11-08. Base develop 159076f. Responsable: Juanma.

## Decisión y alcance

Juanma confirmó usar reconocimiento del navegador para el laboratorio. Se integra SpeechRecognition/webkitSpeechRecognition en alta y edición de pacientes, en español es-AR. La disponibilidad del servicio depende del navegador, permisos y conexión; la escritura manual siempre permanece disponible. No se promete funcionamiento offline ni procesamiento local: el navegador puede enviar audio a su proveedor. La ayuda visible explica dictar, revisar y añadir el texto; las limitaciones del proveedor se documentan aquí y en la guía interna.

Alternativas descartadas para este incremento: contratar una API externa sin contrato definido y exigir reconocimiento local con compatibilidad insuficiente. No se copia el fallback del prototipo que insertaba historias clínicas prefabricadas.

## Flujo

1. Inicio explícito del médico; nunca se solicita micrófono al abrir la página.
2. Se muestran resultados provisionales, separados de las frases finales. La lista acumulativa se reconstruye para no duplicar resultados.
3. Detener espera finales/end; si el proveedor no responde, se aborta tras 4 segundos, conservando solo finales. El inicio tiene timeout de 12 segundos. No hay reinicio automático.
4. El médico revisa/edita el borrador final y elige añadirlo al resumen o descartarlo. Añadir preserva el texto previo y agrega dos saltos de línea. El límite combinado es 20000 caracteres; no se trunca silenciosamente.
5. Guardar/validar se bloquea durante captura o mientras exista un borrador no vacío pendiente. Después de añadir se usa el guardado normal. Salir desmonta el componente y aborta; eventos tardíos se ignoran. Los borradores se pierden al salir o recargar, igual que los campos no guardados del formulario.

## Datos y permisos

No se almacena audio ni borrador en el backend, localStorage o sessionStorage. Solo el texto incorporado se envía como clinical_summary por POST/PUT /api/patients. Se reutilizan permisos médicos, validaciones, control de versión e historial existentes. No se agregan tablas ni migraciones. No se crean estudios, diagnósticos o cuentas. La clave React por patientId evita que una sesión de dictado se arrastre entre formularios de distintos pacientes.

## Implementación y verificación

Revisión adicional: el editor permanece visible al vaciar el borrador para permitir reescribirlo. El formulario completo se monta con una clave por patientId: al navegar entre fichas, descarta estados del paciente anterior, aborta su dictado y espera la nueva carga. Esto corrige un riesgo preexistente de mostrar/guardar datos anteriores mientras se cargaba otro paciente. Se prueban esa transición con respuesta diferida y los callbacks tardíos de una sesión anterior.

ClinicalDictation.jsx encapsula el proveedor y su ciclo de vida; dictation.css aporta el panel. PatientForm.jsx conecta el borrador aceptado al resumen y bloquea el submit pendiente. Pruebas de componente y de integración simulan eventos de voz, permisos, red, timeout, cancelación, edición y límites. La precisión/compatibilidad del micrófono real requiere prueba manual; no se afirma que esté verificada por las pruebas DOM.

Referencias: [SpeechRecognition](https://developer.mozilla.org/en-US/docs/Web/API/SpeechRecognition), [guía Web Speech](https://developer.mozilla.org/en-US/docs/Web/API/Web_Speech_API/Using_the_Web_Speech_API). La API tiene disponibilidad limitada; presencia del constructor no garantiza disponibilidad del servicio. El texto siempre requiere revisión médica.

Validación manual: Juanma confirmó el funcionamiento el 10/11/2026 tras el fallo inicial en Brave. El mensaje de conexión orienta a probar Chrome y solo informa frases conservadas cuando existen. Se retiró del formulario el aviso de datos de demostración por solicitud de Juanma; esto no modifica los datos del catálogo ni convierte códigos DEMO en SNOMED.
