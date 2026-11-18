# Integraciones clínicas

## Responsabilidades y flujo

El navegador usa la API autenticada de Exoma Care. El backend agrega las credenciales del proveedor; no se envían al frontend.

| Servicio | Función | Qué se conserva en Exoma Care |
| --- | --- | --- |
| SNOMED | Buscar términos y códigos de síntomas | Concepto seleccionado, código textual, etiqueta e ID local estable |
| Apigen | Consultar identidad genética, genes y herencia; crear patologías del grupo | Código y grupo asociados a una patología local |
| CDSS | Consultar criterios externos y orientación por síntomas SNOMED | Criterios solo al guardar explícitamente; orientación transitoria |
| Familiograma | Dibujar la familia guardada | SVG validado, PDF, autor y versiones de ficha/familia |

La validación local sigue exigiendo un cardinal **o** dos secundarios de cada patología seleccionada. CDSS tiene su propia regla y estrategia: una respuesta sin compatibilidad no invalida automáticamente una sospecha local. Las sospechas del paciente no se envían como diagnósticos confirmados al familiograma.

## Configuración

Completar `back/.env`, ignorado por Git. No usar variables `VITE_` para credenciales.

| Variables | Uso |
| --- | --- |
| `SNOMED_URL`, `SNOMED_API_KEY`, `SNOMED_REGION` | Endpoint de síntomas, clave y región (`us-east-1`) |
| `API_GEN_URL`, `APIGEN_API_KEY` | Base REST y clave Apigen; también se admite `API_SECRET_KEY_API_GEN` |
| `APIGEN_GROUP_ID` | Grupo del catálogo genético, por defecto `grupo6` |
| `CDSS_BASE_URL`, `CDSS_API_KEY` | Base `/api/v1` y clave de orientación |
| `FAMILIOGRAM_BASE_URL`, `FAMILIOGRAM_API_KEY` | Base de la función familiograma y clave |
| `JWT_SECRET_KEY` | Autenticación local y firma de selecciones SNOMED |

Reiniciar el backend después de cambiar configuración. Las credenciales de estos servicios son independientes de las claves de la API de cupones.

### Bases que probaron las integraciones antes de unir la rama con develop

La numeración original de esta rama (`0014`/`0015`) coincidía con una migración distinta de develop. No cambiar manualmente `alembic_version` ni borrar la base. Antes de `alembic upgrade head`, inspeccionar desde `back`:

```bash
./.venv/Scripts/python.exe -m app.infrastructure.database.reconcile_clinical_revision
```

Si detecta una base clínica anterior al merge, detener el backend y ejecutar:

```bash
./.venv/Scripts/python.exe -m app.infrastructure.database.reconcile_clinical_revision --apply --backup "D:/Downloads/exoma-care-antes-integracion.db"
```

La ruta de respaldo debe ser nueva y estar fuera del repositorio. La herramienta valida el esquema original, respalda SQLite, agrega la migración de estudios que faltaba y registra la revisión equivalente. Conserva las tablas clínicas y sus datos. Si el esquema no coincide, se detiene. Una base procedente de develop no requiere esta conversión. Alembic bloquea la actualización directa de una base clínica antigua para impedir que se aplique una migración con significado equivocado.

Con el backend detenido y un respaldo de la base, ejecutar desde `back` en Git Bash:

```bash
./.venv/Scripts/python.exe -m pip install -r requirements.txt
./.venv/Scripts/python.exe -m alembic current
./.venv/Scripts/python.exe -m alembic upgrade head
bash dev.sh
```

La migración `0014` corresponde a estudios y presupuestos de develop. `0015` agrega identidad externa a patologías y restricciones de unicidad; `0016` agrega detalles familiares y documentos. No se borran patologías, familiares ni revisiones. La conversión a PDF utiliza `fpdf2`, ya incluido en dependencias.

En otra terminal, desde `front`:

```bash
npm install
npm run dev
```

## Terminología

El selector compartido busca exclusivamente en SNOMED. La búsqueda remota requiere tres caracteres. La selección explícita importa el concepto con un ID local; repetir el mismo código reutiliza ese ID. La etiqueta proviene del servidor, mediante una selección firmada por usuario y con vencimiento de quince minutos. Una selección vencida requiere repetir la búsqueda.

Los conceptos históricos DEMO ya seleccionados se conservan, pero no se ofrecen en nuevas búsquedas. Actualizar los criterios del catálogo mediante el borrador CDSS o selección SNOMED antes de usar nuevas fichas con criterios reales. No se reinterpretan como SNOMED ni se envían a CDSS. La búsqueda no interpreta negaciones ni transforma automáticamente el resumen clínico en síntomas.

## Catálogo e identidad externa

El gerente consulta Apigen y CDSS desde el catálogo. Primero guarda o selecciona una definición local; luego asocia la identidad genética y, si corresponde, el código CDSS. La asociación no reemplaza síntomas ni modifica revisiones de pacientes. Una identidad externa no puede asignarse a dos definiciones locales y no puede reemplazarse desde esta pantalla una vez guardada.

Los criterios de CDSS pueden prepararse explícitamente como borrador: se importan los conceptos, se elige un único cardinal y se revisan los secundarios. Los demás cardinales externos no se convierten en secundarios. Solo **Guardar** modifica la definición local. Los conceptos importados pueden permanecer en el catálogo local aunque se descarte el borrador.

El alta genética en Apigen es una operación externa separada. Requiere código, nombre, genes, herencia y confirmación. Si la respuesta se pierde, consultar el catálogo antes de reintentar: el alta pudo completarse. No existe una transacción conjunta entre Apigen y la base local. No se habilitan automáticamente todas las patologías externas ni se modifica la estrategia del grupo CDSS.

## Orientación CDSS

En el formulario de paciente, seleccionar síntomas y pulsar **Consultar orientación CDSS**. Se envían únicamente códigos SNOMED de conceptos almacenados. El resultado muestra compatibilidad, estrategia y coincidencias; el profesional elige las sospechas manualmente. Cambiar los síntomas descarta la orientación anterior. La caída del servicio no impide continuar con la validación local.

## Familia y documentos

Para generar, guardar primero los familiares. Cada familiar requiere nombres y apellidos separados y parentesco del generador; sexo, edad y fallecimiento describen su representación. Los nombres históricos no se dividen automáticamente. Para ubicar ramas materna/paterna, completar los progenitores y su sexo; el proveedor puede rechazar estructuras ambiguas.

Se envía exactamente un paciente y la versión guardada de sus antecedentes. El paciente se representa con sexo no identificado porque la ficha actual no registra ese dato. La regla de sospecha del generador permanece desactivada. Solo diagnósticos familiares conocidos se envían como diagnósticos; los códigos locales sin identidad genética conservan un prefijo local.

El proveedor devuelve SVG. El backend valida el contenido y lo convierte a un PDF real. Los archivos quedan asociados al paciente, autor y versiones de ficha/familia. Si estas cambian durante la generación, se rechaza el guardado con conflicto; si cambian después, el documento se muestra desactualizado y se conserva como histórico. Las descargas requieren autenticación de médico y comprueban la asociación al paciente.

## Rutas nuevas

Todos los caminos comienzan en `/api`. Las respuestas exactas se consultan en `/docs` del backend.

| Método y ruta | Acceso |
| --- | --- |
| `GET /terminology/symptoms?q=...&limit=10` | Médico/gerente |
| `POST /terminology/symptoms/import` | Médico/gerente |
| `GET /clinical-integrations/apigen/pathologies` | Médico/gerente |
| `GET /clinical-integrations/apigen/genes?q=...` | Gerente |
| `POST /clinical-integrations/apigen/pathologies` | Gerente |
| `PUT /clinical-integrations/pathologies/{id}/identity` | Gerente |
| `GET /clinical-integrations/cdss/pathologies` | Médico/gerente |
| `POST /clinical-integrations/cdss/pathologies/{code}/draft` | Gerente |
| `POST /clinical-integrations/cdss/advice` | Médico/gerente |
| `GET /patients/{id}/familiogram/relationships` | Médico |
| `GET /patients/{id}/familiogram` | Médico |
| `POST /patients/{id}/familiogram` | Médico |
| `GET /patients/{id}/familiogram/{document_id}/{format}` | Médico; formato `pdf` o `svg` |

Errores: 401/403 para acceso; 404 para recursos inexistentes; 422 para entradas o estructura familiar inválidas; 409 para conflictos de versión o alta genética duplicada; 502/503 para fallos externos según la operación. Un fallo externo no se presenta como diagnóstico negativo.

## Prueba manual

Usar datos ficticios y respaldar la base antes de migrar.

1. **Gerente, catálogo:** abrir una patología existente. Consultar catálogos externos; revisar genes/herencia y los criterios CDSS. Asociar la identidad correcta y verificar que se conservan el ID y los criterios locales. Recargar y comprobar persistencia.
2. **Criterios:** preparar criterios de una patología CDSS, elegir un cardinal, usar el borrador y guardar. Revisar antes los criterios, porque este guardado modifica futuras validaciones locales. Confirmar que las revisiones históricas no cambian.
3. **SNOMED:** buscar un síntoma con tres o más caracteres en el origen SNOMED, seleccionarlo y comprobar etiqueta/código. Repetir la selección en otra ficha y verificar que no se duplica. Comprobar que los conceptos históricos ya guardados siguen visibles.
4. **Paciente/CDSS:** seleccionar síntomas SNOMED, consultar orientación y cambiar uno. La respuesta anterior debe desaparecer. Probar una sospecha que cumpla la regla local y comprobar que la orientación no sustituye esa validación.
5. **Familia:** completar nombres/apellidos, progenitores y parentescos detallados. Guardar; generar; abrir imagen y PDF. Ambos deben mostrar nombres y símbolos legibles. El botón de generación queda deshabilitado mientras se edita la familia.
6. **Versiones:** modificar y guardar un familiar; el documento anterior debe aparecer desactualizado. Generar otro y comprobar que se conservan ambos. Con dos pestañas, una versión antigua debe producir un conflicto sin sobrescribir la nueva.
7. **Fallos y permisos:** con credencial externa ausente o inválida, debe aparecer un error comprensible y mantenerse la información local. Un paciente no puede acceder a las rutas clínicas o documentos de familiares.
8. **Alta Apigen opcional:** probar únicamente si se desea crear realmente una patología externa de prueba del grupo. Consultar primero si el código existe. Después asociarlo a una definición local; no esperar soporte CDSS automático.

## Verificación automatizada

Desde `back`: `./.venv/Scripts/python.exe -m pytest -q`.
Desde `front`: `node --test --test-concurrency=1 tests/*.test.mjs`, `npm run lint`, `npm run build`.
Las pruebas usan proveedores simulados y bases temporales. El contrato del proveedor puede evolucionar; comprobar las integraciones reales con datos sintéticos cuando cambie.

CDSS admite hasta 60 segundos de espera de lectura (70 segundos en el cliente web). Si vence, se informa la demora y se permite reintentar; no se realiza un reintento automático. Para generar un familiograma se indican los familiares sin nombres, apellidos o parentesco detallado y se deshabilita el botón hasta completarlos.
