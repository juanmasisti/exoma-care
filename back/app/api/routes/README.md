# Rutas HTTP

Routers de FastAPI organizados por recurso o funcionalidad de la API. Aquí se
esperan módulos con esquemas de entrada/salida, rutas, códigos HTTP y traducción
de errores de aplicación a respuestas HTTP. Mantener la validación del
transporte aquí; las decisiones de negocio corresponden a `use_cases/`.

Actualmente `auth.py` contiene el endpoint de inicio de sesión.
