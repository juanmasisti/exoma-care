"""Alta de la solicitud de estudio (EC-10) y emisión del presupuesto (EC-11)."""

from collections.abc import Iterable
from typing import Any

from app.domain.entities.budget import (
    calculate_budget,
    combine_genes,
    normalize_gene,
    to_cents,
)
from app.domain.entities.roles import UserRole
from app.domain.entities.study_request import GeneRef, PathologyRef
from app.domain.entities.user import AuthenticatedUser
from app.domain.interfaces.gene_catalog import GeneCatalogGateway
from app.domain.interfaces.study_request_repository import StudyRequestRepository
from app.use_cases.study_request_errors import StudyRequestConflictError
from app.use_cases.study_request_views import (
    NO_ACCESS_MESSAGE,
    budget_to_dict,
    ensure_can_view,
    study_detail,
    study_summary,
)

# Límite de sugerencias que se piden a Apigen al validar un gen agregado a mano.
GENE_LOOKUP_LIMIT = 50


def _unique_codes(codes: Iterable[str]) -> tuple[str, ...]:
    seen: dict[str, None] = {}
    for code in codes:
        normalized = code.strip().upper()
        if not normalized:
            raise ValueError("El código de patología no puede estar vacío.")
        seen.setdefault(normalized, None)
    if not seen:
        raise ValueError("Elegí al menos una patología.")
    return tuple(seen)


class StudyRequestService:
    def __init__(self, repo: StudyRequestRepository, genes: GeneCatalogGateway):
        self._repo = repo
        self._genes = genes

    # --- Catálogo para armar la solicitud (Apigen) ---

    async def catalogo(self) -> list[dict[str, Any]]:
        return [
            {
                "code": item["codigo"],
                "name": item.get("nombre") or item["codigo"],
                "genes": list(combine_genes(item["genes"])) if item["genes"] else [],
            }
            for item in await self._genes.listar_patologias()
        ]

    async def buscar_genes(self, prefijo: str) -> list[str]:
        return await self._genes.buscar_genes(prefijo)

    # --- EC-10: alta de la solicitud ---

    async def crear(
        self,
        *,
        physician_id: int,
        patient_id: int,
        pathology_codes: Iterable[str],
        additional_genes: Iterable[str] = (),
        include_secondary_findings: bool = False,
    ) -> dict[str, Any]:
        codes = _unique_codes(pathology_codes)
        if not self._repo.patient_exists(patient_id):
            raise LookupError("El paciente no existe.")

        catalog = {
            item["codigo"].strip().upper(): item
            for item in await self._genes.listar_patologias()
        }
        pathologies: list[PathologyRef] = []
        gene_groups: list[list[str]] = []
        for code in codes:
            item = catalog.get(code)
            if item is None:
                raise ValueError(f"La patología {code} no existe en el catálogo de genes.")
            pathologies.append(
                PathologyRef(code=item["codigo"], name=item.get("nombre") or item["codigo"])
            )
            gene_groups.append(item["genes"])

        # Los genes de varias patologías se unen sin repetir; no se infiere ninguna relación médica.
        catalog_genes = combine_genes(*gene_groups)
        already = set(catalog_genes)
        manual_genes = tuple(
            symbol for symbol in combine_genes(additional_genes) if symbol not in already
        )
        for symbol in manual_genes:
            await self._ensure_gene_exists(symbol)

        genes = tuple(GeneRef(symbol, "catalogo") for symbol in catalog_genes) + tuple(
            GeneRef(symbol, "manual") for symbol in manual_genes
        )
        # Falla si no hay ningún gen: sin genes no hay nada que presupuestar.
        calculate_budget(gene.symbol for gene in genes)

        study = self._repo.create_study(
            patient_id=patient_id,
            physician_id=physician_id,
            include_secondary_findings=include_secondary_findings,
            pathologies=pathologies,
            genes=genes,
        )
        self._repo.commit()
        return study_detail(self._repo, study)

    async def _ensure_gene_exists(self, symbol: str) -> None:
        found = await self._genes.buscar_genes(symbol, limit=GENE_LOOKUP_LIMIT)
        if symbol not in {normalize_gene(candidate) for candidate in found}:
            raise ValueError(f"El gen {symbol} no existe en el catálogo de genes.")

    # --- Consultas ---

    def obtener(self, study_id: int, actor: AuthenticatedUser) -> dict[str, Any]:
        study = self._study(study_id)
        ensure_can_view(self._repo, study, actor)
        return study_detail(self._repo, study)

    def listar(self, actor: AuthenticatedUser) -> list[dict[str, Any]]:
        if actor.role is UserRole.TREATING_PHYSICIAN:
            studies = self._repo.list_studies(physician_id=actor.id)
        elif actor.role in (UserRole.LAB_ADMINISTRATOR, UserRole.SUPER_ADMIN):
            studies = self._repo.list_studies()
        elif actor.role is UserRole.PATIENT:
            patient_id = self._repo.patient_id_for_user(actor.id)
            studies = (
                self._repo.list_studies(patient_id=patient_id)
                if patient_id is not None
                else []
            )
        else:
            raise PermissionError(NO_ACCESS_MESSAGE)
        return [
            study_summary(study, self._repo.patient_full_name(study.patient_id))
            for study in studies
        ]

    # --- EC-11: presupuesto ---

    def emitir_presupuesto(
        self, study_id: int, actor: AuthenticatedUser
    ) -> dict[str, Any]:
        study = self._study(study_id)
        if study.status != "creado":
            raise StudyRequestConflictError(
                "El presupuesto solo se emite para estudios en estado 'creado'."
            )
        if self._repo.get_budget(study_id) is not None:
            raise StudyRequestConflictError("El estudio ya tiene un presupuesto emitido.")
        priced = calculate_budget(gene.symbol for gene in study.genes)
        budget = self._repo.create_budget(
            study_id=study_id,
            gene_count=priced.gene_count,
            base_cents=to_cents(priced.base_amount),
            extra_genes=priced.extra_genes,
            extra_cents=to_cents(priced.extra_amount),
            total_cents=to_cents(priced.total),
            currency=priced.currency,
            issued_by_user_id=actor.id,
        )
        self._repo.commit()
        return budget_to_dict(budget, None)

    def obtener_presupuesto(
        self, study_id: int, actor: AuthenticatedUser
    ) -> dict[str, Any]:
        study = self._study(study_id)
        ensure_can_view(self._repo, study, actor)
        budget = self._repo.get_budget(study_id)
        if budget is None:
            raise LookupError("El estudio todavía no tiene presupuesto.")
        return budget_to_dict(budget, self._repo.get_coverage_request(study_id))

    def _study(self, study_id: int):
        study = self._repo.get_study(study_id)
        if study is None:
            raise LookupError("El estudio no existe.")
        return study
