# Configuración local compartida

Fecha: 2026-10-28.

## Decisión

API, migraciones y cargadores leen configuración mediante `app/config.py`,
con pydantic-settings, ya declarado en requirements.txt. Se busca `back/.env`
mediante una ruta absoluta calculada desde el módulo. Se permite sobrescribir
sus valores con variables del proceso para pruebas y otros entornos.

`DATABASE_URL` mantiene el valor por defecto SQLite de la base recibida.
`JWT_SECRET_KEY` debe contener al menos 32 bytes; se obtiene mediante una
misma función para emisión y verificación de tokens. Se representa como
SecretStr y no se incluyen valores de entrada en errores de configuración.
La ausencia de clave no impide preparar migraciones, pero impide firmar JWT.

## Operación

Se versiona `.env.example` sin clave y se ignora `.env`. Cada integrante prepara
su archivo local; no se comparte el secreto de otro desarrollador ni se copia
al frontend. La clave se genera una vez, no al iniciar cada terminal.
Cambiarla invalida tokens anteriores. Reiniciar el backend después de cambiar
configuración, en particular la conexión que se crea al importar el módulo.

No se ejecutan migraciones al iniciar el servidor ni se sobreescriben archivos
locales existentes. Las guías personales y la configuración particular de la
demostración de Juanma permanecen fuera de la documentación compartida.
