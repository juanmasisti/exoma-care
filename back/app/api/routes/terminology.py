from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session
from app.api.catalog_dependencies import require_roles
from app.api.dependencies import get_database_session
from app.api.routes.pathologies import SymptomResponse
from app.config import get_jwt_secret, get_settings
from app.domain.entities.roles import UserRole
from app.domain.entities.user import AuthenticatedUser
from app.infrastructure.external_services.errors import ExternalServiceError
from app.infrastructure.external_services.snomed_client import SnomedClient
from app.use_cases.terminology import Terminology

router = APIRouter(prefix='/api/terminology', tags=['terminología SNOMED'])
clinical_user = require_roles(UserRole.MEDICAL_MANAGER, UserRole.TREATING_PHYSICIAN)


def get_terminology():
    settings = get_settings()
    try:
        client = SnomedClient(settings.snomed_api_key.get_secret_value(), url=settings.snomed_url, region=settings.snomed_region)
    except ValueError:
        raise HTTPException(503, 'El servicio SNOMED no está configurado.') from None
    return Terminology(client, get_jwt_secret())


class SelectionRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    selection_token: str = Field(min_length=1, max_length=2048)


@router.get('/symptoms')
async def search_symptoms(q: str = Query(min_length=3, max_length=100), limit: int = Query(default=10, ge=1, le=50), user: AuthenticatedUser = Depends(clinical_user), service: Terminology = Depends(get_terminology)):
    try:
        return await service.search(q, limit, user.id)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None
    except ExternalServiceError as exc:
        raise HTTPException(503, str(exc)) from None


@router.post('/symptoms/import', response_model=SymptomResponse)
def import_symptom(body: SelectionRequest, user: AuthenticatedUser = Depends(clinical_user), service: Terminology = Depends(get_terminology), session: Session = Depends(get_database_session)):
    try:
        return service.import_selection(body.selection_token, user.id, session)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None
