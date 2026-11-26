
# Exoma Care

**Sistema de gestión de estudios de exoma clínico**

Proyecto académico de la materia Taller de Tecnologías de Producción de Software orientado al análisis, diseño y desarrollo de una solución para gestionar el circuito de estudios de exoma clínico.

## Descripción

Exoma Care busca representar el flujo de trabajo asociado a un estudio de exoma clínico, desde el registro del paciente y la solicitud médica hasta el seguimiento del estudio y la consulta de sus resultados.

El diseño de la solución se elaboró a partir del relevamiento con el Product Owner, el análisis del dominio, el glosario Léxico Extendido del Lenguaje (LEL) y los escenarios del dominio.

## Objetivos

- Modelar los requerimientos y las reglas de negocio del dominio.
- Facilitar la gestión de pacientes y solicitudes de estudios.
- Representar los procesos vinculados con la información genética, el seguimiento de los estudios y sus resultados.
- Desarrollar una solución coherente con los requerimientos relevados.

## Perfiles contemplados

Según el alcance definido para el sistema, se consideran perfiles como:

- Médico tratante.
- Paciente.
- Administrativo del laboratorio.
- Bioinformático.
- Gerente médico.
- Administrador general.
- Transportista.

## Estado del proyecto

La etapa de relevamiento de requerimientos y elaboración del prototipo de solución fue realizada. Este repositorio se utilizará para organizar el código fuente, la documentación y los cambios correspondientes a las siguientes etapas del proyecto.

## Tecnologías

Las tecnologías y herramientas definitivas se documentarán a medida que se consolide la implementación.

## Autenticación del backend

El backend expone `POST /api/auth/login`. Para ejecutarlo desde `back`, configura
la variable de entorno `JWT_SECRET_KEY` con una clave aleatoria segura y luego
inicia la aplicación con `uvicorn app.main:app`. El endpoint devuelve un token
Bearer; para usuarios con rol Paciente también devuelve
`redirect_to: "/paciente/dashboard"`.

## Organización del repositorio

El repositorio separa el frontend (`front`) del backend (`back`). Cada carpeta
propia del proyecto tiene un `README.md` que describe su responsabilidad y qué
archivos se esperan allí. Los directorios generados o administrados por
herramientas (`node_modules`, `.venv`, `dist` y cachés) no forman parte de esta
arquitectura.

- [Frontend](./front/README.md): aplicación React y Vite.
- [Backend](./back/README.md): API FastAPI organizada por capas.

En el frontend, `features` contiene funcionalidades completas de páginas y sus
elementos propios. `components` se reserva para piezas de interfaz genéricas y
reutilizables; un `widget` representa una parte funcional más específica que
puede compartirse entre páginas. Si solo se usa dentro de una funcionalidad,
debe permanecer dentro de esa feature.

## Equipo

Proyecto desarrollado en equipo por cuatro integrantes en el marco de una actividad académica.

## Datos y seguridad

Este repositorio es público. Se utilizarán datos ficticios para demostraciones y pruebas.

No deben incluirse datos reales de pacientes, credenciales, tokens, claves de API ni archivos con información sensible.
