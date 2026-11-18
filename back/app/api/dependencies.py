"""FastAPI dependency providers."""

from collections.abc import Generator

from fastapi import Depends
from sqlalchemy.orm import Session

from app.config import (
    get_apigen_api_key,
    get_apigen_base_url,
    get_cdss_api_key,
    get_cdss_base_url,
    get_notification_api_key,
    get_notifications_base_url,
)
from app.infrastructure.external_services.apigen_client import ApigenClient
from app.infrastructure.external_services.cdss_client import CDSSClient
from app.infrastructure.database.session import SessionLocal
from app.infrastructure.external_services.notification_client import (
    TTPSNotificationClient,
)
from app.infrastructure.repositories.sqlalchemy_user_repository import (
    SQLAlchemyUserRepository,
)
from app.infrastructure.repositories.sqlalchemy_study_repository import (
    SQLAlchemyStudyRepository,
)
from app.infrastructure.repositories.sqlalchemy_notification_log_repository import (
    SQLAlchemyNotificationLogRepository,
)
from app.use_cases.authentication import AutenticarUsuarioUseCase
from app.use_cases.notifications import EnviarNotificacionUseCase
from app.use_cases.bioinformatics import (
    BuscarVariantesApigenUseCase,
    FinalizarAnalisisBioinformaticoUseCase,
    IniciarAnalisisEstudioUseCase,
    ListarHistorialEstudiosUseCase,
    ListarEstudiosBioinformaticaUseCase,
    ObtenerCatalogoPatologiasUseCase,
    ObtenerResultadoEstudioUseCase,
    ReenviarAvisoResultadoUseCase,
)


def get_database_session() -> Generator[Session, None, None]:
    with SessionLocal() as session:
        yield session


def get_authenticate_user_use_case(
    session: Session = Depends(get_database_session),
) -> AutenticarUsuarioUseCase:
    repository = SQLAlchemyUserRepository(session)
    return AutenticarUsuarioUseCase(repository)


def get_apigen_client() -> ApigenClient:
    return ApigenClient(
        api_key=get_apigen_api_key(),
        base_url=get_apigen_base_url(),
    )


def get_cdss_client() -> CDSSClient:
    return CDSSClient(
        api_key=get_cdss_api_key(),
        base_url=get_cdss_base_url(),
    )


def get_notification_service() -> TTPSNotificationClient:
    return TTPSNotificationClient(
        api_key=get_notification_api_key(),
        base_url=get_notifications_base_url(),
    )


def get_enviar_notificacion_use_case(
    session: Session = Depends(get_database_session),
    notification_service: TTPSNotificationClient = Depends(get_notification_service),
) -> EnviarNotificacionUseCase:
    return EnviarNotificacionUseCase(
        notification_service,
        SQLAlchemyNotificationLogRepository(session),
    )


def get_obtener_catalogo_patologias_use_case(
    cdss: CDSSClient = Depends(get_cdss_client),
) -> ObtenerCatalogoPatologiasUseCase:
    return ObtenerCatalogoPatologiasUseCase(cdss)


def get_listar_estudios_bioinformatica_use_case(
    session: Session = Depends(get_database_session),
) -> ListarEstudiosBioinformaticaUseCase:
    return ListarEstudiosBioinformaticaUseCase(SQLAlchemyStudyRepository(session))


def get_listar_historial_estudios_use_case(
    session: Session = Depends(get_database_session),
) -> ListarHistorialEstudiosUseCase:
    return ListarHistorialEstudiosUseCase(SQLAlchemyStudyRepository(session))


def get_iniciar_analisis_estudio_use_case(
    session: Session = Depends(get_database_session),
) -> IniciarAnalisisEstudioUseCase:
    return IniciarAnalisisEstudioUseCase(SQLAlchemyStudyRepository(session))


def get_buscar_variantes_apigen_use_case(
    session: Session = Depends(get_database_session),
    apigen: ApigenClient = Depends(get_apigen_client),
) -> BuscarVariantesApigenUseCase:
    return BuscarVariantesApigenUseCase(SQLAlchemyStudyRepository(session), apigen)


def get_finalizar_analisis_bioinformatico_use_case(
    session: Session = Depends(get_database_session),
    apigen: ApigenClient = Depends(get_apigen_client),
    notifications: EnviarNotificacionUseCase = Depends(
        get_enviar_notificacion_use_case
    ),
) -> FinalizarAnalisisBioinformaticoUseCase:
    return FinalizarAnalisisBioinformaticoUseCase(
        SQLAlchemyStudyRepository(session),
        apigen,
        notifications,
    )


def get_obtener_resultado_estudio_use_case(
    session: Session = Depends(get_database_session),
) -> ObtenerResultadoEstudioUseCase:
    return ObtenerResultadoEstudioUseCase(SQLAlchemyStudyRepository(session))


def get_reenviar_aviso_resultado_use_case(
    session: Session = Depends(get_database_session),
    notifications: EnviarNotificacionUseCase = Depends(
        get_enviar_notificacion_use_case
    ),
) -> ReenviarAvisoResultadoUseCase:
    return ReenviarAvisoResultadoUseCase(
        SQLAlchemyStudyRepository(session),
        notifications,
    )
