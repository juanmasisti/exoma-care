# EC21-PREP — Preparación del chatbot de pacientes (EC-21)

Fecha: 11/11/2026. Responsable: Juanma. Base: develop f02e26e.

> Documento histórico de preparación. El contrato vigente está en ec21-integracion-genlab.md; los límites y ejemplos de esta etapa fueron reemplazados.

## Alcance y decisión

El plan transversal asigna EC-21 a Juanma. La entrevista corregida (p. 31) pide enviar la pregunta del paciente al chatbot externo especializado en las cinco patologías y mostrar su respuesta, sin atención humana ni modelo propio.

Juanma confirmó preparar la integración mientras el otro equipo entrega su API: probablemente un POST y Supabase, pero todavía sin contrato. Se elige una interfaz de proveedor inyectable; no se inventan URL, claves, campos externos ni respuestas clínicas. Supabase no determina si el endpoint será RPC o Edge Function ni su autenticación.

Se descartó implementar un cliente HTTP especulativo o un chatbot simulado en la aplicación. UnconfiguredChatbot informa indisponibilidad real y no hace solicitudes. No hay bandera para habilitar respuestas falsas. Los dobles de proveedor solo viven en tests.

## Contrato interno de Exoma Care

Ambas rutas requieren el JWT habitual de Exoma Care y rol `patient`:

| Método y ruta | Entrada | Salida |
|---|---|---|
| GET /api/chatbot/status | Sin cuerpo | `{ "available": false }` hasta conectar el proveedor |
| POST /api/chatbot/messages | `{ "question": "¿Qué es Fabry?" }` | `{ "answer": "Respuesta del proveedor" }` solo si está integrado |

El estado indica configuración, no una comprobación remota de salud. La pregunta debe ser string, se recortan espacios exteriores, admite 1–2000 caracteres y no acepta campos adicionales. Respuesta válida: texto no vacío de hasta 16000 caracteres. Estos límites son decisiones internas, ajustables al contrato externo.

Errores: 401 sin sesión, 403 otro rol, 422 entrada inválida, 503 integración no disponible, 502 fallo/respuesta inválida del proveedor y 504 timeout. Los errores de integración usan `detail: {code, message}` sin exponer errores crudos del proveedor. Timeout servicio: 20s; cliente React: 25s. No hay reintentos automáticos. Los resultados usan `Cache-Control: no-store`.

## Interfaz y datos

Ruta `/paciente/consultas`, accesible desde portal y menú del paciente. Comprueba disponibilidad; permite volver a comprobar después de un error. Si está disponible, admite una consulta en curso, conserva pregunta al fallar y muestra respuesta como texto sin interpretar HTML. Salir cancela la solicitud del navegador e ignora resultados tardíos; eso no garantiza cancelar un procesamiento ya recibido por el servicio remoto.

El historial visual vive en memoria durante la pantalla y se descarta al salir o cambiar sesión. Cada pregunta se envía por separado: no se envían mensajes anteriores, identidad ni ficha clínica. No hay tablas nuevas, migraciones, localStorage ni almacenamiento de conversaciones en Exoma Care. El tratamiento de datos por el proveedor aún debe relevarse.

## Conectar cuando llegue el contrato

1. Confirmar URL, autenticación, cuerpo/respuesta, errores, límites, timeout y si requiere conversación o streaming.
2. Implementar un adaptador en infraestructura que cumpla `ChatbotProvider.available` y `async answer(question) -> str`, usando un cliente HTTP asíncrono. Configuración y secretos solo en backend. Una cancelación debe propagarse sin ocultarla.
3. Sustituir UnconfiguredChatbot en `get_chatbot_service`; ampliar configuración y `.env.example` con los nombres realmente necesarios.
4. Probar el contrato externo, errores y flujo real antes de declarar EC-21 integrado. Si requiere historial o streaming, revisar la decisión, no fingir que el contrato actual los soporta.

## Verificación

Tests backend cubren permisos, normalización, validaciones, indisponibilidad, respuesta, límite, errores y cancelación por timeout. Tests frontend cubren navegación, recuperación, preservación de pregunta, no interpretación de HTML, envío pendiente, salida y cambio de sesión. La integración real sigue pendiente del proveedor.

Actualización: las decisiones provisionales de esta preparación se reemplazan por [EC21-GenLab](ec21-integracion-genlab.md) tras recibir el contrato real de GenLab.
