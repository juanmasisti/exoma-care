# Interfaces del dominio

Contratos (por ejemplo, `Protocol`) requeridos por los casos de uso para
colaborar con recursos externos. Se esperan interfaces de repositorio y otros
puertos abstractos; las implementaciones concretas pertenecen a
`infrastructure/`.

`notification_service.py` define el puerto de notificaciones. El caso de uso
depende de este contrato y no de la API externa.
