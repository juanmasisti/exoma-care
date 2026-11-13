# Cliente del módulo de optimización de recorridos (T04a)

Fecha: 13/11/2026. Área de logística (Ivo).

## Por qué existe

La orden del día (T04) necesita el orden de visita de los centros, y ese orden lo calcula el
módulo 9 de otro grupo. Antes de T04 se deja listo y probado el cliente, con un endpoint mínimo
para mostrarlo en la demo.

## Contrato (presentación del grupo)

`POST https://optimizacionapi.vercel.app/api/optimizacion`, sin clave. Cuerpo
`{"coordenadas": [{"lat": ..., "lon": ...}, ...]}`; responde el mismo formato reordenado. El
primer punto es la partida y el último el destino; solo ordena los del medio. No devuelve ids.

## Qué se hizo

- `RouteOptimizer` (Protocol) y `RouteOptimizerError` en `app/domain/interfaces/route_optimizer.py`.
- `RouteOptimizerClient` en `app/infrastructure/adapters/` con `httpx` (ya estaba en las
  dependencias) y **timeout de 5 s**. Caída, timeout, 4xx/5xx o respuesta con otra forma →
  `RouteOptimizerError` con un mensaje legible.
- `RoutePreviewService.order_centers(ids)` (`app/use_cases/routes.py`): arma
  `[laboratorio, centros..., laboratorio]` y vuelve a cada centro por su lat/lon con una
  tolerancia de `1e-6` (unos 10 cm), por si la API redondea distinto.
  - Con 0 o 1 centros no se llama a la API.
  - Si la respuesta tiene otra cantidad de puntos, no empieza y termina en el laboratorio o
    trae un punto que no es de ningún centro pedido → error. **Nunca se inventa un orden propio.**
- Configuración (`app/config.py`, `.env`): `RECORRIDOS_API_URL`, `CENTRAL_LAB_LATITUDE` y
  `CENTRAL_LAB_LONGITUDE`, con valores por defecto (la URL es pública y no hay clave).
- Endpoint `POST /api/transport/route-preview`: errores 404 (centro inexistente o inactivo),
  422 (ids repetidos o más de 100) y 502 (error del módulo de recorridos).

## Decisiones

- **Partida y destino: el Laboratorio Central**, Calle 62 N° 555, La Plata (B1904),
  `-34.921559, -57.938362`. Sigue **abierto** si el transportista arranca en el laboratorio o
  en otro lado (pregunta para el profesor). Si cambia, basta con cambiar la configuración.
- **Rol provisorio `lab_administrator`**: el rol `transporter` todavía no existe (Camila, EC-03)
  y no se tocan los roles de otra área. Cuando exista, se cambia `transporter` en
  `app/api/routes/transport.py`.
- **Endpoint provisorio para la demo**: recibe los ids de los centros. En T04 los centros
  salen de la orden del día y este endpoint se quita o se reemplaza.

## Pruebas

`tests/test_route_preview_api.py`: un doble del Protocol (`dependency_overrides` de
`get_route_optimizer`) para el orden, 0/1 centros sin llamada, el error de la API, el punto
desconocido, la respuesta mal formada y los permisos; el adaptador se prueba con
`httpx.MockTransport`. Ninguna prueba sale a internet.
