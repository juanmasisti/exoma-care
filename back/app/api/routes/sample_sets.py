from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_database_session
from app.api.routes.shipments import get_sample_set_closed_handler
from app.domain.interfaces.sample_set_hooks import SampleSetAssigner, SampleSetClosedHandler
from app.infrastructure.repositories.sqlalchemy_sample_repository import SQLAlchemySampleRepository
from app.infrastructure.repositories.sqlalchemy_sample_set_repository import SQLAlchemySampleSetRepository
from app.use_cases.sample_sets import SampleSetService

router = APIRouter(prefix="/api/sample-sets", tags=["sample sets"])


def get_service(session: Session = Depends(get_database_session),
                closed_handler: SampleSetClosedHandler = Depends(get_sample_set_closed_handler)) -> SampleSetService:
    return SampleSetService(SQLAlchemySampleSetRepository(session), SQLAlchemySampleRepository(session), closed_handler)


# Enganche que usa la llegada (T04) con Depends: corre en la sesión del pedido y no confirma nada.
def get_sample_set_assigner(service: SampleSetService = Depends(get_service)) -> SampleSetAssigner:
    return service
