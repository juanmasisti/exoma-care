# Catálogo de patologías (EC-06)

## Alcance y permisos

El gerente médico crea y edita patologías. Médico tratante y gerente consultan
el catálogo y validan sospechas clínicas individuales. Los otros perfiles no
acceden a estos endpoints. La API verifica JWT y consulta el rol actual en BD.
Este control es un apoyo mínimo al catálogo; primer acceso y segundo factor
siguen siendo tareas de Camila. No se presentan como implementados.

## Preparación de BD

Desde `back`, con el entorno activado:

```sh
python -m alembic upgrade head
```

0001 reproduce las tablas de la base recibida; 0002 agrega el catálogo. No se
ejecutan migraciones ni se cargan datos automáticamente al iniciar la API.
Si ya hay tablas creadas por el seeder previo, comparar primero su esquema
con 0001 y respaldar los datos. Solo si coincide exactamente se puede marcar
esa base con `python -m alembic stamp 0001` y luego aplicar `upgrade head`.
No usar stamp para ocultar diferencias de esquema ni borrar bases existentes.

Para una demostración optativa con conceptos ficticios:

```sh
python -m app.infrastructure.database.seed_catalog_demo
```

Los códigos DEMO no son SNOMED. No se incluyen relaciones reales entre las
cinco patologías del relevamiento y síntomas: necesitan el catálogo confirmado.
El cargador no crea usuarios ni patologías y puede repetirse sin duplicados.

## API

Todos los endpoints requieren `Authorization: Bearer <token>`.
El token se obtiene mediante el login existente con email y contraseña.

| Operación | Endpoint | Permisos |
| --- | --- | --- |
| Buscar conceptos (máximo 100 por consulta) | GET /api/symptoms?q=texto | Médico y gerente |
| Listar patologías | GET /api/pathologies | Médico y gerente |
| Consultar una patología | GET /api/pathologies/{id} | Médico y gerente |
| Crear | POST /api/pathologies | Gerente |
| Editar | PUT /api/pathologies/{id} | Gerente |
| Validar sospecha clínica individual | POST /api/pathologies/{id}/validate-suspicion | Médico y gerente |

Crear/editar recibe `name`, `cardinal_symptom_id` y `secondary_symptom_ids`.
El nombre se normaliza en espacios y se compara sin distinguir mayúsculas.
Un secundario repetido se almacena una sola vez. Cardinal y secundarios no
pueden superponerse. Todos los IDs deben existir en terminología.

La validación recibe `symptom_ids` y devuelve `valid`, `criterion`,
`matched_cardinal` y `matched_secondary_ids`. Sus criterios son `cardinal`,
`two_secondary` e `insufficient_symptoms`. No diagnostica ni confirma un alta.
IDs desconocidos devuelven error, no se descartan silenciosamente.

Errores: 401 sesión inválida, 403 permiso insuficiente, 404 inexistente,
409 nombre duplicado y 422 configuración o entrada inválida.

## Límite histórico

Editar una patología afecta validaciones futuras. Al implementar EC-07 se
deberá conservar la evidencia/configuración usada al validar un paciente para
no reinterpretar automáticamente su historia con una configuración posterior.
Esta entrega todavía no registra validaciones de pacientes.

## Verificación

Desde `back`: `python -m pytest -q`. Se prueban la regla, persistencia en
SQLite, migraciones, endpoints, login real y permisos con datos ficticios.

## Frontend y ejecución local

Desde `back`, definir `JWT_SECRET_KEY` con un secreto aleatorio de al menos
32 bytes y opcionalmente `DATABASE_URL`; ejecutar las migraciones y luego
`python -m uvicorn app.main:app --host 127.0.0.1 --port 8000`.
Desde `front`, ejecutar `npm ci` y `npm run dev`.
Vite reenvía `/api` a 127.0.0.1:8000, por lo que el navegador usa el mismo
origen. En un despliegue se deberá configurar su proxy equivalente.

El formulario existente ahora usa email, como el backend. La respuesta del
login conserva `rol` como etiqueta y agrega `role` con el código estable.
Gerente y médico acceden a `/catalogo/patologias`. Los demás portales aún no
están implementados; no se presentan como funcionales.

El token permanece solo en memoria. Recargar o cerrar la pestaña termina la
sesión local; el cierre de sesión descarta el token, no lo revoca en servidor.
Un 401 elimina la sesión y devuelve al login. No hay persistencia de sesión,
recuperación de contraseña, primer acceso ni segundo factor en esta entrega.
Se quitó la casilla visual de recordar dispositivo porque todavía no funciona.
Estos límites deben coordinarse con Camila antes de ampliar autenticación.

Pruebas frontend: `npm test`, `npm run lint` y `npm run build` desde `front`.
Se usa el runner integrado de Node y happy-dom, solo como dependencia de
desarrollo. Las pruebas renderizan componentes React e interactúan con sus
controles; simulan respuestas HTTP. Las pruebas de backend verifican aparte
login, permisos y persistencia real con bases temporales. No equivalen a una
revisión visual o una prueba completa de navegador.
