# Casos de uso

Operaciones de aplicación que coordinan el dominio y los contratos de
infraestructura para cumplir una acción del usuario o del sistema. Se esperan
clases o funciones con entradas y salidas claras, y errores de aplicación
explícitos. No deben conocer los detalles HTTP; los routers adaptan sus
resultados a respuestas.

Actualmente `authentication.py` implementa la autenticación de usuarios.
`notifications.py` contiene el caso de uso reutilizable para enviar un aviso y
guardar su referencia externa para auditoría.
Al finalizar un análisis bioinformático se avisa al paciente y al médico
asociado con un mensaje genérico, sin incluir datos genéticos en el correo.
