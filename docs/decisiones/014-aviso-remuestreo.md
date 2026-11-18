# Aviso de remuestreo por mail (T03c, EC-16)

Fecha: 17/11/2026. Área de logística (Ivo).

## Qué se hizo

- `EmailResampleNotifier` (`back/app/infrastructure/email_resample_notifier.py`) reemplaza a
  `LoggingResampleNotifier` (provisorio de la decisión 011, borrado). Manda el aviso con
  `EnviarNotificacionUseCase` de Camila, sin llamar a su cliente HTTP directo, a los
  destinatarios de `SQLAlchemyStudyRepository.notification_recipients`.
- `ResampleNotifier.avisar_remuestreo` recibe además `sample_id`, para la clave de idempotencia.
- Contrato en [logística](../logistica.md#aviso-de-remuestreo-por-mail-t03c). Sin migraciones y
  sin cambios en el código de avisos.

## Qué se decidió

- **`asyncio.run` para llamar al caso de uso async desde el webhook sync.** El webhook es
  `def`: FastAPI lo corre en un hilo del threadpool, sin event loop. `asyncio.run` crea un loop
  en ese hilo y corre ahí el envío y el log de avisos, que hace `commit` con la misma sesión del
  pedido. Se descartó `anyio.from_thread.run`: corre la coroutine en el hilo del loop principal,
  así que la sesión cambia de hilo y el commit de SQLite bloquea el loop de toda la app mientras
  dura; además solo funciona desde hilos creados por anyio (no desde un script, una prueba o un
  hilo común). El cliente de avisos abre un `httpx.AsyncClient` por pedido, así que un loop
  nuevo por aviso no le afecta.
- **El caso de uso de avisos se arma al avisar, no con `Depends`.** `get_enviar_notificacion_use_case`
  pide la clave al construirse: como dependencia, sin `NOTIFICATIONS_API_KEY` el webhook y los
  `GET` de seguimiento (comparten `get_service`) darían 500. Se llama a esa misma función desde
  una `lambda`, con la sesión del pedido; si falla, cae en `_notify`, que ya lo loguea.
- **Si el mail falla, el webhook responde igual 201** (como en la decisión 011): el aviso se
  manda después del commit y un error no deshace lo guardado.
- **Destinatarios**: el paciente siempre; el médico si `notification_recipients` lo trae. A
  diferencia del aviso de resultado, no se exige el médico. Sin mail del paciente no se manda
  (el servicio exige al menos un destinatario) y queda un warning.
- **`idempotency_key = remuestreo-{study_id}-{sample_id}`**: un remuestreo por muestra. Un aviso
  repetido del bot no vuelve a avisar (devuelve el resultado original antes de llegar acá).
- **Contenido**: código del estudio, motivo y que hay que sacar un turno nuevo, sin volver a
  pagar (decisión 011). Sin nombre ni DNI. El motivo de bioinformática es texto libre de hasta
  500 caracteres y va tal cual: quien llama a `solicitar_remuestreo` no debería poner datos
  clínicos ahí (avisarle a Camila).
- **El notifier tipa el caso de uso con un `Protocol` local (`Avisos`)** en vez de importar
  `EnviarNotificacionUseCase`, para no invertir capas (infraestructura → casos de uso).

## Pendiente y abierto

- Si `solicitar_remuestreo` se llamara alguna vez desde código `async` (con un loop corriendo en
  el hilo), `asyncio.run` falla: se loguea y no se manda. Hoy nadie lo llama (Camila no tiene
  camino de ADN insuficiente); si lo suma desde un endpoint `async`, conviene pasarlo a
  `run_in_threadpool` o agregar una variante async del notifier. Regla: llamar a
  `solicitar_remuestreo` desde rutas `def` (o desde un hilo sin loop).
- El envío bloquea el pedido hasta que avisos responde: con el timeout (10 s) y los 2
  reintentos del cliente de Camila, si avisos está lento el webhook puede tardar 30 s o más en
  dar 201. Si el bot corta y reintenta, recibe 200 por idempotencia y no se avisa de nuevo.
- Un mail que falla no se reintenta solo: queda en el log. Reenviarlo sería otra tarea.
- Comentario para Camila (no bloqueante): `get_enviar_notificacion_use_case` resuelve la clave
  al construirse, así que cualquier endpoint que dependa de él da 500 sin `NOTIFICATIONS_API_KEY`.
