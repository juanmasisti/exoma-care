# Documentos del turno: orden de extracción y consentimiento en PDF (T02b)

Fecha: 13/11/2026. Área de logística (Ivo).

## Qué se hizo

- `GET /api/appointments/{id}/documents/{kind}` (`kind` = `order` | `consent`), solo rol
  `patient`. Contrato en [logística](../logistica.md#documentos-del-turno-t02b).
- `AppointmentService.turno_para_documentos`: turno inexistente o de otro paciente da 404 (como
  cancelar); turno que no está `booked` da 409. Los documentos de un turno cancelado no sirven
  para presentarse.
- El repositorio de turnos suma nombre, apellido y DNI del paciente al registro del turno. Es
  la misma lectura provisoria de `patients` de T02a (decisión 005); los endpoints de turnos no
  exponen esos datos.
- PDF en `app/infrastructure/appointment_documents.py`. Se genera en cada pedido y no se guarda.
- Front: botones "Descargar orden" y "Descargar consentimiento" en "Día de extracción".

## Qué se decidió

- **`fpdf2`** como dependencia nueva: es Python puro (solo arrastra Pillow y fontTools), no
  necesita programas del sistema y alcanza para texto simple. Otras opciones, como
  WeasyPrint, piden bibliotecas nativas que en Windows complican la instalación.
- **Hora argentina**: el PDF formatea `starts_at` tal como lo devuelve el repositorio, que ya
  lo convierte con `logistics.TIMEZONE`, la misma zona que usa el turnero. No hay una segunda
  conversión. Una prueba fija que un turno de las 9:00 imprime "09:00" y no "12:00" (UTC).
- **Fuente Helvetica** (incluida en el PDF estándar, sin archivos de fuente): cubre los acentos
  y la ñ, pero solo latin-1. Un carácter fuera de ese rango en un dato cargado (por ejemplo,
  un apellido con "Ş") se imprime como "?" en vez de romper el PDF. Si hace falta escribirlo
  bien, se agrega una fuente TTF.
- **Descarga por axios con `responseType: 'blob'`**, no con un enlace: la sesión manda el token
  en el header `Authorization`. Con blob, el error del back también llega como Blob; `api.js`
  lo lee para que `errorMessage` muestre el `detail`.
- `kind` inválido da 422, por la validación de FastAPI con `Literal`.

## Pendiente y abierto

- **Texto del consentimiento**: el PO dijo que tiene una plantilla y que la iba a pasar
  (entrevista, 16:28). Hasta tenerla, el PDF lleva un texto corto y genérico marcado como
  PROVISORIO. No se inventó texto legal. Pregunta para el PO: ¿nos pasa la plantilla y qué
  datos del paciente o del estudio tiene que traer completos?
- **Código del estudio** `EST-000001`: sigue provisorio (decisión abierta 4 del dominio).
- **Datos del paciente**: hoy, nombre, apellido y DNI leídos directo de `patients`. Cuando
  pacientes ofrezca su servicio, se lee de ahí.
