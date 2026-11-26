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
python -m seeders concepts
```

Los códigos DEMO no son SNOMED. No se incluyen relaciones reales entre las
cinco patologías del relevamiento y síntomas: necesitan el catálogo confirmado.
El cargador no crea usuarios ni patologías y puede repetirse sin duplicados.
Para cargar las cinco patologías iniciales de demostración, ejecutar
`python -m seeders catalog` desde `back`.

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

Crear/editar recibe `name`, `cardinal_symptom_ids` (uno o más) y `secondary_symptom_ids`. Se acepta el campo singular anterior para clientes existentes, pero no ambos formatos en una misma solicitud.
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

Editar una patología afecta validaciones futuras. EC-07 conserva la evidencia y
configuración usada en cada revisión del paciente. Cambiar los criterios no
reinterpreta ni reescribe las revisiones anteriores. Al editar una ficha se valida
contra los criterios actuales.

## Verificación

Desde `back`: `python -m pytest -q`. Se prueban la regla, persistencia en
SQLite, migraciones, endpoints, login real y permisos con datos ficticios.

## Frontend y ejecución local

Desde `back`, copiar `.env.example` como `.env`, completar `JWT_SECRET_KEY`
con un secreto aleatorio de al menos 32 bytes y configurar `DATABASE_URL` si
corresponde. La configuración se lee automáticamente; las variables del proceso
tienen prioridad sobre el archivo. Ejecutar las migraciones y luego
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


## SNOMED, CDSS y configuración local

SNOMED identifica los conceptos seleccionados. CDSS ofrece asociaciones y una
orientación con su propia estrategia. La validación para guardar sigue la regla
local de al menos un cardinal o dos secundarios de cada patología seleccionada.
Una respuesta no compatible de CDSS no reemplaza esa validación.

El archivo `back/seeders/clinical_pathologies.json` registra los criterios de
origen y las identidades genéticas verificadas. No contiene credenciales. Se conservan todos los cardinales de origen; ninguno se transforma en secundario. Pompe incluye hipotonía y miocardiopatía hipertrófica como alternativas cardinales.

### Actualización explícita del catálogo

Con el backend detenido, respaldar la base y aplicar las migraciones según la
guía de integraciones. Desde `back`:

```bash
./.venv/Scripts/python.exe -m seeders catalog-upgrade
./.venv/Scripts/python.exe -m seeders catalog-upgrade --apply
```

El primer comando solo inspecciona: no migra ni crea la base. Exige una base
existente en la revisión actual. `--apply` crea definiciones faltantes y sustituye
solo configuraciones que coincidan con el seed DEMO original completo. Los
resultados `conservar_personalizada` y `conflicto_identidad` requieren revisión del
gerente y no se sobrescriben. Toda la aplicación se ejecuta en una transacción.

Se conservan IDs, conceptos DEMO anteriores y revisiones clínicas/familiares.
Al editar un paciente histórico puede ser necesario volver a seleccionar sus
síntomas con SNOMED para validar los criterios actuales. No hay conversión
automática entre conceptos por semejanza de sus nombres.

### Verificación manual

1. Usar una copia de la base. Inspeccionar antes de aplicar y comparar los cambios.
2. Comprobar que los criterios personalizados no cambiaron y que los históricos siguen visibles.
3. Repetir la operación: no debe duplicar patologías ni conceptos.
4. Como médico, validar un cardinal, dos secundarios y un síntoma ajeno.
5. Como superadministrador, abrir directamente `/medico/pacientes` y
   `/catalogo/patologias`: debe redirigir a administración, sin consultar APIs clínicas.
6. Como médico/gerente, verificar consulta del catálogo; solo gerente puede editar.


## Cardinales múltiples y preparación inicial

La migración `0020` agrega cardinales adicionales y conserva el cardinal original.
No modifica pacientes ni snapshots. Una patología exige al menos un cardinal;
cualquiera de ellos satisface la regla. El downgrade se rechaza si hay cardinales
adicionales para evitar pérdida de criterios. Los campos singulares de respuesta
se mantienen por compatibilidad; el frontend utiliza `cardinal_symptoms`.

En una base nueva, `python -m seeders` carga el archivo versionado sin consultar
servicios externos. El seed normal nunca reemplaza criterios existentes. En una
base antigua, respaldar, migrar hasta head y usar `catalog-upgrade` para revisar y
aplicar la conversión de criterios DEMO. El archivo DEMO anterior solo se conserva
como referencia de reconocimiento y fixture de pruebas.

Prueba de Pompe: seleccionar únicamente hipotonía debe validar; seleccionar
únicamente miocardiopatía hipertrófica también. Dos secundarios distintos deben
validar; un secundario repetido no. El historial anterior conserva sus criterios.


## Preparación manual para probar la rama

Desde `back`, en Git Bash, para una base nueva separada:

```bash
export DATABASE_URL=sqlite:///./exoma_catalogo_prueba.db
./.venv/Scripts/python.exe -m seeders
bash dev.sh
```

Usar un nombre de archivo que no exista si se quiere comenzar desde cero. El seed
muestra la contraseña del paciente solo al crearlo. Mantener `DATABASE_URL` en la
misma terminal al iniciar el backend. Desde `front`: `npm run dev`.

Para una base existente, detener el backend y respaldarla antes de migrar:

```bash
./.venv/Scripts/python.exe -m app.infrastructure.database.reconcile_clinical_revision
./.venv/Scripts/python.exe -m alembic upgrade head
./.venv/Scripts/python.exe -m seeders catalog-upgrade
./.venv/Scripts/python.exe -m seeders catalog-upgrade --apply
```

Si la inspección de revisión clínica informa una base antigua incompatible,
resolver primero la reconciliación con respaldo según `integraciones-clinicas.md`;
no continuar directamente con `upgrade head`. No ejecutar `stamp` para saltarla.

En el catálogo del gerente, Pompe debe mostrar ambos cardinales. En una ficha
clínica nueva, seleccionar solo uno y comprobar la validación. Repetir con el otro,
con dos secundarios distintos y con un único secundario. Revisar una ficha antigua:
sus conceptos e historial deben permanecer intactos. Una patología personalizada
puede quedar sin actualizar: el informe lo indica y el gerente decide sus criterios.
