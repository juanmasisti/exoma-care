from datetime import date, datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, ConfigDict, Field, PositiveInt

from app.api.catalog_dependencies import require_roles
from app.api.dependencies import (
    get_buscar_variantes_apigen_use_case,
    get_finalizar_analisis_bioinformatico_use_case,
    get_iniciar_analisis_estudio_use_case,
    get_listar_historial_estudios_use_case,
    get_listar_estudios_bioinformatica_use_case,
    get_obtener_catalogo_patologias_use_case,
    get_obtener_resultado_estudio_use_case,
    get_reenviar_aviso_resultado_use_case,
)
from app.domain.entities.roles import UserRole
from app.domain.entities.user import AuthenticatedUser
from app.infrastructure.external_services.errors import ExternalServiceError
from app.infrastructure.study_result_pdf import render_study_result_pdf
from app.use_cases.bioinformatics import (
    ApigenResponseError,
    BioinformaticsStudyConflictError,
    BioinformaticsStudyNotFoundError,
    BioinformaticsResultNotAvailableError,
    BuscarVariantesApigenUseCase,
    FinalizarAnalisisBioinformaticoUseCase,
    IniciarAnalisisEstudioUseCase,
    ListarHistorialEstudiosUseCase,
    ListarEstudiosBioinformaticaUseCase,
    ObtenerCatalogoPatologiasUseCase,
    ObtenerResultadoEstudioUseCase,
    ReenviarAvisoResultadoUseCase,
    NotificationRecipientsUnavailableError,
)

router = APIRouter(
    prefix="/api/bioinformatica",
    tags=["bioinformática"],
)
bioinformatics_roles = require_roles(UserRole.BIOINFORMATICIAN)
pathology_catalog_roles = require_roles(
    UserRole.BIOINFORMATICIAN, UserRole.SUPER_ADMIN
)
result_read_roles = require_roles(
    UserRole.BIOINFORMATICIAN,
    UserRole.TREATING_PHYSICIAN,
    UserRole.PATIENT,
    UserRole.SUPER_ADMIN,
)
svg_read_roles = require_roles(
    UserRole.BIOINFORMATICIAN,
    UserRole.TREATING_PHYSICIAN,
    UserRole.PATIENT,
    UserRole.SUPER_ADMIN,
)


class PathologyCatalogItem(BaseModel):
    codigo: str
    nombre: str


class BioinformaticsStudyResponse(BaseModel):
    id: int
    patient_id: int
    patient_name: str
    patient_dni: str
    status: str
    analyst_id: int | None
    created_at: datetime
    codigo_patologia: str | None = None
    original_study_id: int | None = None  # EC-14: reanálisis del estudio indicado
    genes: list[str] = Field(default_factory=list)
    patient: dict[str, Any] | None = None
    variantes_detectadas: list[dict[str, Any]] | None
    resultado_diagnostico: str | None
    hallazgos_secundarios: list[dict[str, Any]] | None
    fecha_reevaluacion: date | None


class VariantResponse(BaseModel):
    id: int | str
    hgvs_c: str
    proteina: str | None = None
    clasificacion: str


class VariantSearchResponse(BaseModel):
    items: list[VariantResponse]
    total: int
    limit: int
    offset: int


class VariantSelection(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    id: int | str | None = None
    gen: str = Field(min_length=1, max_length=50)
    hgvs_c: str = Field(min_length=1, max_length=200)
    proteina: str | None = Field(default=None, max_length=200)
    clasificacion: Literal[
        "patogenica",
        "probablemente_patogenica",
        "benigna",
        "probablemente_benigna",
        "vus",
    ]


class FinalizeAnalysisRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    codigo_patologia: str = Field(min_length=1, max_length=100)
    variantes: list[VariantSelection] = Field(max_length=1000)


@router.get(
    "/patologias",
    response_model=list[PathologyCatalogItem],
)
async def get_pathology_catalog(
    _actor: AuthenticatedUser = Depends(pathology_catalog_roles),
    use_case: ObtenerCatalogoPatologiasUseCase = Depends(
        get_obtener_catalogo_patologias_use_case
    ),
) -> list[dict[str, str]]:
    try:
        return await use_case.execute()
    except ExternalServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.get(
    "/estudios",
    response_model=list[BioinformaticsStudyResponse],
)
def list_bioinformatics_studies(
    _actor: AuthenticatedUser = Depends(bioinformatics_roles),
    use_case: ListarEstudiosBioinformaticaUseCase = Depends(
        get_listar_estudios_bioinformatica_use_case
    ),
) -> list[dict[str, Any]]:
    return use_case.execute()


@router.get(
    "/historial",
    response_model=list[BioinformaticsStudyResponse],
)
def list_bioinformatics_history(
    q: str = Query(default="", max_length=100),
    _actor: AuthenticatedUser = Depends(bioinformatics_roles),
    use_case: ListarHistorialEstudiosUseCase = Depends(
        get_listar_historial_estudios_use_case
    ),
) -> list[dict[str, Any]]:
    return use_case.execute(q)


@router.patch(
    "/estudios/{study_id}/iniciar",
    response_model=BioinformaticsStudyResponse,
)
def start_bioinformatics_analysis(
    study_id: PositiveInt,
    actor: AuthenticatedUser = Depends(bioinformatics_roles),
    use_case: IniciarAnalisisEstudioUseCase = Depends(
        get_iniciar_analisis_estudio_use_case
    ),
) -> dict[str, Any]:
    try:
        return use_case.execute(study_id, actor.id)
    except BioinformaticsStudyNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except BioinformaticsStudyConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get(
    "/estudios/{study_id}/variantes",
    response_model=VariantSearchResponse,
)
async def search_apigen_variants(
    study_id: PositiveInt,
    gen: str = Query(min_length=1, max_length=50),
    hgvs_c: str | None = Query(default=None, min_length=1, max_length=100),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    actor: AuthenticatedUser = Depends(bioinformatics_roles),
    use_case: BuscarVariantesApigenUseCase = Depends(
        get_buscar_variantes_apigen_use_case
    ),
) -> dict[str, Any]:
    try:
        return await use_case.execute(
            study_id,
            actor.id,
            gen,
            hgvs_c,
            limit,
            offset,
        )
    except BioinformaticsStudyNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except BioinformaticsStudyConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ExternalServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.post(
    "/estudios/{study_id}/resultados",
    response_model=BioinformaticsStudyResponse,
)
async def finalize_bioinformatics_analysis(
    study_id: PositiveInt,
    body: FinalizeAnalysisRequest,
    actor: AuthenticatedUser = Depends(bioinformatics_roles),
    use_case: FinalizarAnalisisBioinformaticoUseCase = Depends(
        get_finalizar_analisis_bioinformatico_use_case
    ),
) -> dict[str, Any]:
    try:
        return await use_case.execute(
            study_id=study_id,
            analyst_id=actor.id,
            codigo_patologia=body.codigo_patologia,
            variantes=[variant.model_dump() for variant in body.variantes],
        )
    except BioinformaticsStudyNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except BioinformaticsStudyConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except NotificationRecipientsUnavailableError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except (ApigenResponseError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ExternalServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.post("/estudios/{study_id}/reenviar-notificacion")
async def resend_result_notification(
    study_id: PositiveInt,
    _actor: AuthenticatedUser = Depends(bioinformatics_roles),
    use_case: ReenviarAvisoResultadoUseCase = Depends(
        get_reenviar_aviso_resultado_use_case
    ),
) -> dict[str, str]:
    try:
        await use_case.execute(study_id)
        return {"mensaje": "Aviso de resultado reenviado correctamente."}
    except BioinformaticsStudyNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except BioinformaticsStudyConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except NotificationRecipientsUnavailableError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ExternalServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.get(
    "/estudios/{study_id}/resultado.svg",
    response_class=Response,
    responses={200: {"content": {"image/svg+xml": {}}}},
)
def export_study_result_svg(
    study_id: PositiveInt,
    actor: AuthenticatedUser = Depends(svg_read_roles),
    use_case: ObtenerResultadoEstudioUseCase = Depends(
        get_obtener_resultado_estudio_use_case
    ),
) -> Response:
    try:
        study = use_case.execute(study_id, actor.id, actor.role)
    except BioinformaticsStudyNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except BioinformaticsResultNotAvailableError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    svg = _study_result_svg(study)
    return Response(
        content=svg,
        media_type="image/svg+xml",
        headers={
            "Content-Disposition": f'attachment; filename="estudio-{study_id}-resultado.svg"'
        },
    )


@router.get(
    "/estudios/{study_id}/resultado.pdf",
    response_class=Response,
    responses={200: {"content": {"application/pdf": {}}}},
)
def export_study_result_pdf(
    study_id: PositiveInt,
    actor: AuthenticatedUser = Depends(result_read_roles),
    use_case: ObtenerResultadoEstudioUseCase = Depends(
        get_obtener_resultado_estudio_use_case
    ),
) -> Response:
    try:
        study = use_case.execute(study_id, actor.id, actor.role)
    except BioinformaticsStudyNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except BioinformaticsResultNotAvailableError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    pdf = render_study_result_pdf(study)
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="estudio-{study_id}-resultado.pdf"'
        },
    )


def _study_result_svg(study: dict[str, Any]) -> str:
    from xml.sax.saxutils import escape

    lines = [
        ("EXOMA CARE - Resultado de estudio", 24, True),
        (f"Estudio: {study['id']}", 16, False),
        (f"Paciente: {study.get('patient_name', 'No disponible')}", 16, False),
        (
            f"Diagnostico: {study.get('resultado_diagnostico') or 'No disponible'}",
            18,
            True,
        ),
        ("Variantes detectadas", 18, True),
    ]
    variants = study.get("variantes_detectadas") or []
    for variant in variants:
        lines.append(
            (
                " - ".join(
                    str(variant.get(field, ""))
                    for field in ("gen", "hgvs_c", "proteina", "clasificacion")
                    if variant.get(field)
                ),
                14,
                False,
            )
        )
    lines.append(("Hallazgos secundarios", 18, True))
    for finding in study.get("hallazgos_secundarios") or []:
        lines.append((str(finding), 14, False))
    reassessment = study.get("fecha_reevaluacion")
    if reassessment:
        lines.append((f"Fecha de reevaluacion: {reassessment}", 14, False))

    row_height = 30
    height = 48 + row_height * len(lines)
    text_elements = []
    for index, (text, font_size, bold) in enumerate(lines):
        escaped_text = escape(text)
        weight = " font-weight=\"bold\"" if bold else ""
        text_elements.append(
            f'<text x="32" y="{48 + row_height * index}" '
            f'font-size="{font_size}"{weight}>{escaped_text}</text>'
        )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="{height}" '
        f'viewBox="0 0 1000 {height}">'
        '<rect width="100%" height="100%" fill="white"/>'
        '<g font-family="Arial, sans-serif" fill="#172554">'
        + "".join(text_elements)
        + "</g></svg>"
    )
