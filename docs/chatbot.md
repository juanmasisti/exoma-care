# EC-21 — Guía de funcionamiento y defensa

Actualizada: 15/11/2026. Responsable: Juanma. Proveedor: GenLab, grupo 5.

## Explicación en un minuto

El paciente inicia sesión en Exoma Care y abre Consultas. React envía su pregunta a nuestro backend FastAPI. El backend valida su sesión, exige el rol paciente y delega la consulta a la API externa de GenLab. GenLab genera la respuesta y nuestro sistema la muestra como texto. No entrenamos ni alojamos un modelo de inteligencia artificial: implementamos su integración, los permisos, la conversación y el manejo de errores.

El alcance responde a la entrevista: consultas informativas al servicio especializado externo. No es una consulta con un médico humano ni una herramienta de diagnóstico.

## Recorrido de una pregunta

```text
Paciente → React → FastAPI Exoma Care → GenLab (Supabase)
         ← texto ← respuesta validada ← respuesta + ID + tipo
```

1. Al abrir la pantalla, React consulta GET /api/chatbot/status. FastAPI consulta la salud del proveedor. Si falta configuración o no está disponible, informa el problema; nunca inventa una respuesta.
2. Al enviar, la pregunta aparece inmediatamente, con “Preparando respuesta…” debajo. Se bloquean envíos simultáneos.
3. React usa el JWT de sesión normal para llamar a POST /api/chatbot/messages. FastAPI comprueba identidad y rol patient.
4. Se valida una pregunta de 1 a 1000 caracteres, quitando espacios exteriores. Se rechazan campos adicionales.
5. FastAPI recupera el identificador externo desde una referencia firmada, si es una continuación, y verifica que pertenezca al usuario autenticado.
6. El adaptador llama a GenLab con mensaje y conversacion_id. Las credenciales del servicio solo salen desde nuestro servidor.
7. Se valida la respuesta externa; React muestra el texto sin ejecutar HTML. No hay streaming: la animación indica espera y la respuesta aparece completa.
8. Si falla, se conserva la pregunta para editar/reintentar sin duplicarla. Salir cancela la solicitud del navegador, aunque no garantiza cancelar el trabajo que el proveedor ya recibió.

## Dos APIs y dos autenticaciones

| Tramo | Autenticación | Responsabilidad |
|---|---|---|
| React → FastAPI | JWT de sesión Exoma Care | Identifica al paciente y controla el rol |
| FastAPI → GenLab | headers apikey y x-chatbot-token | Identifican el acceso del grupo al servicio externo |

CHATBOT_URL, CHATBOT_APIKEY y CHATBOT_TOKEN se configuran en back/.env o en el entorno del servidor. .env está ignorado por Git; .env.example solo documenta nombres. No se usan variables VITE_ para estos secretos. No son las claves de nuestra API de cupones.

La integración consume un endpoint HTTP de GenLab alojado en Supabase; no accede directamente a sus tablas ni conoce los detalles internos del modelo. Un GET de salud exitoso no demuestra que las credenciales de POST sean válidas.

## Contratos principales

| Endpoint de Exoma Care | Entrada | Salida |
|---|---|---|
| GET /api/chatbot/status | JWT de sesión, sin cuerpo | available y message |
| POST /api/chatbot/messages | question y conversation_token opcional | answer, conversation_token y kind |

Primera pregunta a nuestra API:
```json
{"question":"¿Qué es un exoma clínico?","conversation_token":null}
```

El adaptador la traduce al contrato externo:
```json
{"mensaje":"¿Qué es un exoma clínico?","conversacion_id":null}
```

GenLab devuelve respuesta, conversacion_id y tipo. Para continuar, el frontend envía el conversation_token recibido de Exoma Care; no el identificador externo libremente elegido.

## Historial y contexto: diferencia clave para la defensa

**Historial visible:** mensajes almacenados en el estado de React, solo mientras está abierta esta pantalla. No se guardan en SQLite ni en localStorage. Al salir, recargar o cambiar sesión, desaparecen. No hay migraciones propias del chatbot.

**Contexto del proveedor:** según su contrato, GenLab recuerda los últimos seis intercambios y olvida la conversación tras 30 minutos de inactividad. Exoma Care envía el identificador para continuar dentro de esa ventana; no reenvía un historial completo.

**Decisión acordada:** mantener conversación temporal en este incremento. No persistir mensajes no era una exigencia de la entrevista: fue una propuesta de implementación, luego conversada y aceptada. Podríamos guardar conversaciones para lectura futura, pero eso no restauraría el contexto externo. El contrato no documenta un mecanismo para reconstruirlo con el historial guardado.

Nueva conversación limpia los mensajes y la referencia local; el siguiente envío comienza sin ID. No borra inmediatamente datos en GenLab: no existe un endpoint de borrado documentado.

## Por qué firmamos la referencia de conversación

GenLab separa conversaciones por grupo, no por paciente de Exoma Care. Para evitar que un usuario presente el ID de otro paciente, encapsulamos ese ID en un JWT firmado por nuestro backend, vinculado al ID del usuario y con expiración de 30 minutos. Se renueva al recibir respuesta.

No es el JWT de login: tiene audiencia exoma-chatbot y emisor exoma-care. Se valida firma, vencimiento y propietario antes de llamar a GenLab. Está firmado, no cifrado; su objetivo es impedir alteración/uso por otro usuario, no ocultar su contenido. Un token vencido exige iniciar otra conversación.

## Qué puede responder

Información general sobre estudios genéticos y Fabry, Gaucher, Pompe, ASMD y mucopolisacaridosis tipo I. El proveedor devuelve cuatro clases:

| Tipo | Significado |
|---|---|
| respuesta | Respuesta informativa dentro de alcance |
| fuera_de_alcance | Consulta ajena al tema |
| derivar_medico | Diagnóstico, resultados personales, síntomas propios o tratamientos |
| sin_informacion | Tema pertinente, pero falta información en su base |

Mostramos el texto del proveedor en todos los casos. No interpretamos resultados ni completamos respuestas con recomendaciones clínicas propias. El contrato declara una base de conocimiento en borrador; preguntas sobre precios, plazos y trámites pueden devolver sin_informacion. No garantizamos exactitud clínica por el solo hecho de recibir HTTP 200.

No enviamos automáticamente ficha clínica, nombre ni resultados. Solo la pregunta y la referencia de conversación. El aviso de no incluir datos personales orienta al usuario; no constituye un detector completo de información sensible.

## Errores y límites

| Situación | Comportamiento |
|---|---|
| 401 de nuestra API | Sesión ausente/vencida; flujo normal de login |
| 403 | El usuario no tiene rol paciente |
| 422 local | Pregunta o cuerpo inválidos |
| 400 | Referencia de conversación inválida, ajena o vencida |
| 429 externo | Esperar Retry-After y reintentar una sola vez desde React |
| 503 externo | Mostrar indisponibilidad y el mensaje público del proveedor |
| 401 externo u otra respuesta inesperada | 502 genérico; no cerrar la sesión local |
| Tiempo agotado | 504, sin reintento automático |

Límite documentado: 20 consultas/minuto por grupo, compartidas por sus pacientes. El backend limita la operación a 20 segundos y React espera hasta 25 segundos por solicitud. No se reintentan timeouts automáticamente porque el proveedor pudo procesar la pregunta. Las respuestas usan Cache-Control: no-store. Se limitan tamaño y formato de la respuesta externa y se rechazan redirecciones HTTP.

## Cuenta de prueba y alta real

El script externo preparar_demo_ec21.py crea un Usuario con rol patient y contraseña aleatoria protegida mediante hash; no crea una ficha Paciente. Si la cuenta ya existe, no cambia su contraseña. Es una ayuda de laboratorio, no el flujo final de registro.

Según la división: Juanma implementa alta clínica EC-07; Camila se ocupa de cuentas, credenciales y primer acceso. Falta coordinar su vinculación y habilitación de acceso. El portal general puede mostrar un acceso provisional; el chatbot se encuentra en /paciente/consultas. No se crean estudios automáticamente.

## Mapa de archivos

| Archivo | Qué explicar |
|---|---|
| back/app/api/routes/chatbot.py | Endpoints, permisos, validación y errores HTTP |
| back/app/use_cases/chatbot.py | Caso de uso y límite de tiempo |
| back/app/domain/interfaces/chatbot_provider.py | Contrato que debe cumplir el proveedor |
| back/app/infrastructure/genlab_chatbot.py | HTTP externo, traducción de campos y errores |
| back/app/infrastructure/chatbot_conversation.py | Referencia firmada por paciente |
| back/app/infrastructure/unconfigured_chatbot.py | Indisponibilidad cuando faltan credenciales |
| back/app/config.py y back/.env.example | Configuración del servidor |
| front/src/features/chatbot/PatientChat.jsx | Pantalla, conversación temporal y espera |
| front/src/features/chatbot/api.js | Llamadas locales y reintento único del 429 |
| front/src/features/chatbot/chatbot.css | Presentación e indicador accesible |
| front/src/App.jsx y ClinicalLayout.jsx | Ruta protegida y navegación |
| back/tests/test_chatbot_api.py, test_genlab.py y front/tests/chatbot.test.mjs | Permisos, contrato, errores y experiencia |

La interfaz de proveedor permite sustituir GenLab sin cambiar la pantalla; los dobles de prueba no son respuestas simuladas en producción.

## Demostración manual

1. Configurar el backend desde el documento privado del grupo 5; nunca copiar claves a esta guía.
2. En Git Bash, desde back: bash dev.sh. Desde front: npm run dev -- --host 127.0.0.1 --port 5173 --strictPort.
3. Iniciar sesión con rol paciente y abrir Consultas. Si falta cuenta, usar el script externo de laboratorio desde back: ./.venv/Scripts/python.exe ../../notas-internas-exoma-care/preparar_demo_ec21.py.
4. Preguntar “¿Qué es un exoma clínico?”. Mostrar pregunta inmediata, indicador y respuesta.
5. Preguntar “¿Y para qué se utiliza?” para mostrar continuidad.
6. Probar una pregunta fuera de alcance y otra que pida diagnóstico, sin datos reales. Explicar que mostramos la respuesta de GenLab, no una frase fija nuestra.
7. Iniciar Nueva conversación; salir y volver para mostrar la temporalidad acordada.
8. En Network comprobar llamadas a nuestro backend, sin credenciales GenLab ni llamadas directas del navegador a Supabase.
9. Para fallos de red, detener el backend y enviar una pregunta: se conserva el texto. No saturar GenLab para provocar un 429; ese caso se verifica con pruebas aisladas.

El chatbot no exige migraciones propias. Otros módulos integrados en develop pueden tener sus propias migraciones y dependencias: seguir también las instrucciones generales del repositorio.

## Preguntas típicas de defensa

- **¿Hicieron la IA?** No. Integramos el servicio del grupo 5 y gestionamos acceso, conversación y fallos.
- **¿Por qué no llamarlo desde React?** Para mantener las credenciales en el servidor, controlar permisos y adaptar el contrato externo.
- **¿Por qué no guardar historial?** Se acordó una conversación temporal; guardar mensajes no recupera la memoria vencida del proveedor.
- **¿Cómo evitan cruzar conversaciones?** Con una referencia firmada y vinculada al paciente autenticado.
- **¿Qué pasa si GenLab cae?** Informamos indisponibilidad o error; preservamos la pregunta, sin fabricar respuestas.
- **¿Puede dar un diagnóstico?** No es el alcance del servicio; esas consultas se orientan al médico.
- **¿Por qué hay dos JWT?** Uno autentica la sesión; el otro protege la referencia de conversación, con propósito y validación diferentes.

Referencias: [decisión vigente](decisiones/ec21-integracion-genlab.md), [preparación histórica](decisiones/ec21-preparacion-chatbot.md), contrato privado GenLab entregado al grupo 6 y entrevista corregida (apartado chatbot).
