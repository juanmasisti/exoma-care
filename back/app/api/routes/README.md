# Rutas HTTP

Routers de FastAPI organizados por recurso o funcionalidad de la API. Aquí se
esperan módulos con esquemas de entrada/salida, rutas, códigos HTTP y traducción
de errores de aplicación a respuestas HTTP. Mantener la validación del
transporte aquí; las decisiones de negocio corresponden a `use_cases/`.

Actualmente `auth.py` contiene el endpoint de inicio de sesión.
`notifications.py` expone endpoints de consulta y health del proveedor,
restringidos al rol `super_admin`.
La ruta `GET /api/bioinformatica/estudios/{id}/resultado.svg` permite descargar
el informe SVG a roles clínicos autorizados.
