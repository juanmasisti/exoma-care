# EC21-GenLab — Chatbot de pacientes conectado a GenLab

Fecha: 11/11/2026. Responsable: Juanma. Rama: feature/chatbot-pacientes.

Sustituye las decisiones provisionales de EC21-PREP sobre proveedor, límite de mensaje y ausencia de contexto. Fuente: contrato privado `Chatbot_GenLab_Datos_de_conexion-G6.md` entregado por grupo 5 y presentación pública https://santiagoc1.github.io/GenLab_Presentacion/#10. El contrato contiene credenciales y NO se copia al repo.

## Arquitectura y configuración

React → FastAPI Exoma Care (JWT, rol patient) → ChatbotService → GenLabChatbot → Supabase de GenLab. El proveedor se configura con CHATBOT_URL, CHATBOT_APIKEY y CHATBOT_TOKEN exclusivamente en back/.env o variables del servidor. Las claves se representan como SecretStr; .env.example contiene campos vacíos. No son las credenciales de cupones. No se usa Authorization Bearer hacia GenLab, sino apikey y x-chatbot-token.

Sin las tres variables se mantiene UnconfiguredChatbot. Configurado, GET /api/chatbot/status realiza un GET sin credenciales al proveedor: `{estado: ok}` habilita la pantalla. Un 503 de salud produce available false y el mensaje público; fallos de conexión producen un error recuperable. Un health exitoso no comprueba las credenciales de POST.

GenLabChatbot concentra traducción de campos y errores. URL HTTPS, sin redirecciones; respuestas limitadas a 128 KiB descomprimidos y texto hasta 16000 caracteres. La respuesta comprimida se decodifica solo una vez. Timeout total de servicio 20s, cliente React 25s para GET y POST. Cancelar en navegador no garantiza interrumpir una consulta ya recibida por GenLab.

## Conversaciones y protección entre pacientes

GenLab separa por grupo, no por usuario de Exoma Care. Por ello el navegador no puede elegir libremente el conversacion_id externo. Nuestro backend lo encapsula en conversation_token firmado con HS256 y JWT_SECRET_KEY, con sub=usuario, aud=exoma-chatbot, iss=exoma-care y expiración de 30 minutos. Cada respuesta renueva el handle. Una referencia ajena, alterada o vencida devuelve 400 antes de llamar al proveedor. No es un token de login ni una credencial de GenLab; está firmado, no cifrado.

El proveedor recuerda los últimos seis intercambios y olvida la conversación tras 30 minutos sin mensajes. El navegador conserva mensajes y handle solo durante la pantalla; nueva conversación, salida y cambio de sesión descartan ese estado. Nueva conversación no borra remotamente: no existe endpoint de borrado documentado.

No se agregan tablas ni migraciones. No se transmiten automáticamente identidad, síntomas, resultados ni ficha clínica. Solo el texto escrito y el identificador de conversación. Se indica al paciente no incluir datos personales; esto no es un filtro capaz de detectar todos los nombres en texto libre.

## Contrato interno actualizado

GET /api/chatbot/status → `{available: boolean, message: string|null}`.

POST /api/chatbot/messages recibe:
```json
{"question":"¿Qué es un exoma clínico?","conversation_token":null}
```
Pregunta string estricta, 1–1000 caracteres después de quitar espacios exteriores. Campos adicionales rechazados. Responde:
```json
{"answer":"Texto del proveedor","conversation_token":"referencia-firmada","kind":"respuesta"}
```
El siguiente POST envía el handle recibido. El adaptador lo traduce a `{mensaje, conversacion_id}`. Las cuatro clases `respuesta`, `fuera_de_alcance`, `derivar_medico` y `sin_informacion` conservan el texto tal cual, sin interpretar HTML y sin agregar contacto con el laboratorio. No se transforma una respuesta 200 de fallback del proveedor en error.

| Situación | Respuesta interna |
|---|---|
| JWT Exoma Care ausente/vencido | 401, comportamiento habitual de sesión |
| Otro rol | 403 |
| Pregunta inválida | 422 local |
| Conversación alterada, ajena o vencida | 400 conversation_invalid; nueva conversación |
| Credenciales GenLab rechazadas (401), 405, 422 externo, 500, respuesta inválida | 502 genérico; NO cerrar sesión ni exponer detalle técnico |
| Límite GenLab 429 | 429 con Retry-After; React espera y reintenta una sola vez |
| GenLab apagado 503 | 503 con detail textual público; sin retry automático |
| Timeout | 504; sin retry automático |

Se respeta Retry-After en segundos o fecha HTTP; si falta/es inválido, 5s. Se normaliza a 1–86400s. El backend no reintenta. React reintenta solo un 429, mantiene un único envío pendiente y aborta la espera al salir. Tras dos 429 muestra error y conserva la pregunta; nunca hay bucle de reintentos. Otros errores conservan pregunta y permiten un nuevo intento manual. No hay garantía de idempotencia ante un timeout: el proveedor puede haber recibido el mensaje.

## Alcance y validación

Asistente informativo de estudios genéticos y las cinco patologías. No diagnostica ni interpreta resultados individuales. El proveedor declara base de conocimiento en borrador y falta de información sobre precios, plazos y trámites; no suplir esas respuestas con texto inventado.

Verificación real 11/11/2026: GET activo, pregunta general sobre exoma clínico y continuación, ambas tipo respuesta, mismo ID de conversación. Sin datos de pacientes. Pruebas aisladas cubren cuatro tipos, headers/body, contexto firmado por usuario, caducidad, errores, gzip y reintento. Juanma confirmó el funcionamiento real del chat el 15/11/2026.

## Ajuste de experiencia y aclaraciones (15/11/2026)

La pregunta aparece inmediatamente en el chat, seguida del indicador de preparación de respuesta (o la espera por límite de consultas). El panel se desplaza al último mensaje. Si falla, se mantiene la pregunta visible y editable para reintentar sin duplicarla; no se simula streaming: GenLab entrega la respuesta completa. La animación respeta la preferencia de movimiento reducido.

La ausencia de historial persistente comenzó como una decisión provisional, no como un requisito recuperado de la entrevista. Juanma acordó mantener la conversación temporal para este incremento tras revisar la diferencia entre historial visible y contexto del proveedor. Guardar conversaciones en nuestra base es una evolución pendiente de decisión; no ampliaría automáticamente la memoria de seis intercambios/30 minutos de GenLab.

La cuenta del script externo preparar_demo_ec21.py es un Usuario con rol patient, sin ficha Paciente creada automáticamente. El alta clínica corresponde a EC-07; invitación/habilitación de acceso se coordina con la responsabilidad de identidad de Camila. El portal completo no se implementa en este ajuste.

Prueba manual del ajuste: enviar una pregunta; comprobar que aparece antes de la respuesta con indicador debajo; comprobar que al responder no se duplica; ante una falla, editar/reintentar y verificar que se conserva el texto. El encabezado explicita estudios genéticos además de las cinco patologías.
