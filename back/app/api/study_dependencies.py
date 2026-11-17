"""Dependencias de FastAPI para solicitudes de estudio, pagos y cupones (EC-10 a EC-13)."""

from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.dependencies import get_apigen_client, get_database_session
from app.config import (
    get_cupones_api_key,
    get_cupones_base_url,
    get_cupones_gerente_id,
    get_obras_sociales_api_key,
    get_obras_sociales_base_url,
)
from app.infrastructure.external_services.apigen_client import ApigenClient
from app.infrastructure.external_services.cupones_client import CuponesClient
from app.infrastructure.external_services.obras_sociales_client import ObrasSocialesClient
from app.infrastructure.repositories.sqlalchemy_study_request_repository import (
    SqlAlchemyStudyRequestRepository,
)
from app.use_cases.coupons import CouponService
from app.use_cases.study_payments import StudyPaymentService
from app.use_cases.study_requests import StudyRequestService


def _unavailable(message: str) -> HTTPException:
    return HTTPException(status_code=503, detail=message)


def get_study_request_repository(
    session: Session = Depends(get_database_session),
) -> SqlAlchemyStudyRequestRepository:
    return SqlAlchemyStudyRequestRepository(session)


def get_cupones_client() -> CuponesClient:
    try:
        return CuponesClient(api_key=get_cupones_api_key(), base_url=get_cupones_base_url())
    except (RuntimeError, ValueError):
        raise _unavailable("El servicio de cupones no está configurado.") from None


def get_obras_sociales_client() -> ObrasSocialesClient:
    try:
        return ObrasSocialesClient(
            api_key=get_obras_sociales_api_key(), base_url=get_obras_sociales_base_url()
        )
    except (RuntimeError, ValueError):
        raise _unavailable("El servicio de obras sociales no está configurado.") from None


def get_study_request_service(
    repo: SqlAlchemyStudyRequestRepository = Depends(get_study_request_repository),
    apigen: ApigenClient = Depends(get_apigen_client),
) -> StudyRequestService:
    return StudyRequestService(repo, apigen)


def get_study_payment_service(
    repo: SqlAlchemyStudyRequestRepository = Depends(get_study_request_repository),
    insurance: ObrasSocialesClient = Depends(get_obras_sociales_client),
    coupons: CuponesClient = Depends(get_cupones_client),
) -> StudyPaymentService:
    return StudyPaymentService(repo, insurance, coupons)


def get_coupon_service(
    repo: SqlAlchemyStudyRequestRepository = Depends(get_study_request_repository),
    gateway: CuponesClient = Depends(get_cupones_client),
) -> CouponService:
    gerente_id = get_cupones_gerente_id()
    if not gerente_id:
        raise _unavailable("Falta configurar CUPONES_GERENTE_ID.")
    return CouponService(repo, gateway, gerente_id)
