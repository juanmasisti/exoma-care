from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field, PositiveInt
from sqlalchemy.orm import Session
from app.api.dependencies import get_database_session
from app.api.routes.family import physician
from app.config import get_settings
from app.domain.entities.user import AuthenticatedUser
from app.domain.interfaces.family_repository import FamilyConflict
from app.infrastructure.external_services.familiogram_client import FamiliogramClient, FamiliogramUnavailable
from app.use_cases.familiogram import FamiliogramService

router = APIRouter(prefix="/api/patients/{patient_id}/familiogram", tags=["familiograma"])

def get_client():
    settings = get_settings()
    key = settings.familiogram_api_key
    return FamiliogramClient(settings.familiogram_base_url, key.get_secret_value() if key else None)

def get_service(session: Session = Depends(get_database_session), client=Depends(get_client)):
    return FamiliogramService(session, client)

def invoke(action):
    try:
        return action()
    except (LookupError, ValueError, FamiliogramUnavailable) as exc:
        code = 404 if isinstance(exc, LookupError) else 409 if isinstance(exc, FamilyConflict) else 503 if isinstance(exc, FamiliogramUnavailable) else 422
        raise HTTPException(code, detail=str(exc)) from None

class GenerateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    patient_version: int = Field(ge=1)
    family_version: int = Field(ge=0)

@router.get("/relationships")
def relationships(patient_id: PositiveInt, actor=Depends(physician), service=Depends(get_service)):
    def run():
        service.patient(patient_id)
        return service.client.relationships()
    return invoke(run)

@router.get("")
def documents(patient_id: PositiveInt, actor=Depends(physician), service=Depends(get_service)):
    return invoke(lambda: service.list(patient_id))

@router.post("", status_code=201)
def generate(patient_id: PositiveInt, body: GenerateRequest, actor: AuthenticatedUser=Depends(physician), service=Depends(get_service)):
    return invoke(lambda: service.generate(patient_id, body.patient_version, body.family_version, actor.id))

@router.get("/{document_id}/{format}")
def download(patient_id: PositiveInt, document_id: PositiveInt, format: str, actor=Depends(physician), service=Depends(get_service)):
    if format not in ("pdf", "svg"):
        raise HTTPException(404)
    row = invoke(lambda: service.document(patient_id, document_id))
    return Response(row.pdf if format == "pdf" else row.svg, media_type="application/pdf" if format == "pdf" else "image/svg+xml",
        headers={"Content-Disposition": f'attachment; filename="familiograma-{patient_id}-{document_id}.{format}"',
                 "Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff", "Content-Security-Policy": "default-src 'none'; sandbox"})
