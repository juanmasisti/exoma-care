# Logística: centros y turnero (EC-15)

Rama: feature/turnos-extraccion, iniciada desde develop. Responsable: Ivo.
Esta decisión reúne las entregas del turnero; cada tarea completa su sección.

## T00a: reglas del turnero

Fecha: 2026-10-30.

- Las reglas puras están en `back/app/domain/entities/logistics.py`. Los turnos son cada
  15 minutos, de 9 a 18 (el último a las 17:45), de lunes a viernes y sin feriados.
- Zona horaria `America/Argentina/Buenos_Aires`. Se agregó `tzdata` a `requirements.txt`
  porque en Windows `zoneinfo` no trae las zonas.
- Un turno que empieza justo en la hora actual ya no se ofrece. La hora actual tiene que
  indicar la zona.
- `fixed_national_holidays` calcula solo los feriados inamovibles de la Ley 27.399,
  incluidos Carnaval y Viernes Santo, que dependen de Pascua. No calcula los trasladables
  (17/6, 17/8, 12/10 y 20/11) ni los puentes turísticos, porque dependen de un decreto
  anual. El Jueves Santo es día no laborable, no feriado.
- Si el Viernes Santo coincide con el 24/3 o el 2/4 (por ejemplo, en 2021), el día queda
  una sola vez con una sola descripción. El turnero lo bloquea igual; solo se pierde el
  nombre del otro feriado.

## T00b: provincias, centros y feriados

Fecha: 2026-10-30. Migración `0004`.

- Tablas `provinces` (nombre único), `extraction_centers` (nombre único por provincia,
  índice en `province_id`, `active` verdadero por defecto) y `holidays` (el día es la clave).
  Los centros son tercerizados y no son usuarios del sistema.
- Seed optativo y repetible `seed_demo_extraction_centers`. Las 24 jurisdicciones y sus
  capitales son reales y las coordenadas, aproximadas. Los nombres, direcciones y teléfonos
  de los centros son ficticios y dicen "DEMO". Las coordenadas de cada centro son las de su
  capital, desplazadas 0,002° (unos 200 m) por centro para que no se superpongan en el mapa.
  Cada provincia indica en el JSON (`offset`) hacia dónde se desplazan, para alejarse de
  ríos, lagunas y costas. Se verificó con OpenStreetMap que ninguno cae en el agua y que
  todos quedan dentro de su ciudad. CABA usa "Ciudad de Buenos Aires" como ciudad, para no
  confundirla con la provincia de Buenos Aires.
- **El reparto de los 100 centros por provincia es un dato DEMO, no una regla.** Las
  fuentes no lo indican. Se repartieron en forma aproximada según la población: Buenos Aires
  20, CABA 10, Córdoba y Santa Fe 8, Mendoza 5, Tucumán 4, nueve provincias con 3 y nueve
  con 2.
- El seed carga los feriados fijos del año actual y del siguiente. Los trasladables y los
  puentes se pueden cargar a mano en `holidays`. El seed agrega lo que falta y no modifica
  ni borra nada: conserva un centro desactivado y un feriado con otra descripción.
- Si otra rama también usa la migración `0004`, se resuelve con `alembic merge` al integrar.

## T00c: API de centros y horarios libres (pendiente)

A completar en T00c: endpoints, permisos y cómo se combinan los feriados de la tabla con
las reglas de T00a.

## Pendiente

- Quién carga cada año los feriados trasladables, los puentes y los feriados fijos de los
  años siguientes (hoy: volver a correr el seed y cargar el resto a mano).
