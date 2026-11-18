"""Permisos de lectura y armado de respuestas de la solicitud de estudio (EC-10 a EC-13)."""

from typing import Any

from app.domain.entities.budget import calculate_budget, split_amounts, to_cents
from app.domain.entities.roles import UserRole
from app.domain.entities.study_request import CoverageRequest, StudyBudget, StudyRequest
from app.domain.entities.user import AuthenticatedUser
from app.domain.interfaces.study_request_repository import StudyRequestRepository

NO_ACCESS_MESSAGE = "No tenés acceso a este estudio."


def ensure_can_view(
    repo: StudyRequestRepository, study: StudyRequest, actor: AuthenticatedUser
) -> None:
    """Administrativo y super admin ven todo; el médico, sus estudios; el paciente, los suyos."""
    if actor.role in (UserRole.LAB_ADMINISTRATOR, UserRole.SUPER_ADMIN):
        return
    if actor.role is UserRole.TREATING_PHYSICIAN and study.physician_id == actor.id:
        return
    if (
        actor.role is UserRole.PATIENT
        and repo.patient_id_for_user(actor.id) == study.patient_id
    ):
        return
    raise PermissionError(NO_ACCESS_MESSAGE)


def ensure_patient_owner(
    repo: StudyRequestRepository, study: StudyRequest, actor: AuthenticatedUser
) -> int:
    """Devuelve el id del paciente si el actor es el paciente dueño del estudio."""
    if actor.role is UserRole.PATIENT:
        patient_id = repo.patient_id_for_user(actor.id)
        if patient_id is not None and patient_id == study.patient_id:
            return patient_id
    raise PermissionError(NO_ACCESS_MESSAGE)


def coverage_to_dict(coverage: CoverageRequest) -> dict[str, Any]:
    # Las URLs de simulación funcionan como credencial: nunca salen del backend.
    return {
        "status": coverage.status,
        "insurer_external_id": coverage.insurer_external_id,
        "rejection_reason": coverage.rejection_reason,
        "demands_count": coverage.demands_count,
        "created_at": coverage.created_at,
        "resolved_at": coverage.resolved_at,
    }


def _split_view(
    budget: StudyBudget, coverage: CoverageRequest | None
) -> dict[str, Any] | None:
    if budget.payment_mode == "particular":
        return {
            "insurer_cents": 0,
            "patient_cents": budget.total_cents,
            "estimated": False,
        }
    if budget.payment_mode == "obra_social":
        confirmed = coverage is not None and coverage.status == "autorizada"
        if confirmed and budget.insurer_cents is not None and budget.patient_cents is not None:
            return {
                "insurer_cents": budget.insurer_cents,
                "patient_cents": budget.patient_cents,
                "estimated": False,
            }
        if budget.coverage_percent is not None:
            split = split_amounts(budget.total_cents, budget.coverage_percent)
            return {
                "insurer_cents": split.insurer_cents,
                "patient_cents": split.patient_gross_cents,
                "estimated": True,
            }
    return None


def budget_to_dict(
    budget: StudyBudget, coverage: CoverageRequest | None
) -> dict[str, Any]:
    return {
        "id": budget.id,
        "study_id": budget.study_id,
        "currency": budget.currency,
        "gene_count": budget.gene_count,
        "base_cents": budget.base_cents,
        "extra_genes": budget.extra_genes,
        "extra_cents": budget.extra_cents,
        "total_cents": budget.total_cents,
        "issued_by_user_id": budget.issued_by_user_id,
        "issued_at": budget.issued_at,
        "payment_mode": budget.payment_mode,
        "insurer": (
            {"id": budget.insurer_external_id, "name": budget.insurer_name}
            if budget.insurer_external_id
            else None
        ),
        "coverage_percent": budget.coverage_percent,
        "coverage_confirmed": coverage is not None and coverage.status == "autorizada",
        "split": _split_view(budget, coverage),
    }


def study_summary(study: StudyRequest, patient_name: str | None = None) -> dict[str, Any]:
    return {
        "id": study.id,
        "patient_id": study.patient_id,
        "patient_name": patient_name,
        "physician_id": study.physician_id,
        "status": study.status,
        "include_secondary_findings": study.include_secondary_findings,
        "created_at": study.created_at,
        "pathologies": [{"code": p.code, "name": p.name} for p in study.pathologies],
        "gene_count": len(study.genes),
    }


def study_detail(repo: StudyRequestRepository, study: StudyRequest) -> dict[str, Any]:
    estimate = None
    if study.genes:
        priced = calculate_budget(gene.symbol for gene in study.genes)
        estimate = {
            "gene_count": priced.gene_count,
            "total_cents": to_cents(priced.total),
            "currency": priced.currency,
        }
    budget = repo.get_budget(study.id)
    coverage = repo.get_coverage_request(study.id)
    return {
        **study_summary(study, repo.patient_full_name(study.patient_id)),
        "genes": [{"symbol": g.symbol, "origin": g.origin} for g in study.genes],
        "result": repo.get_bioinformatics_result(study.id),
        "estimated_budget": estimate,
        "budget": budget_to_dict(budget, coverage) if budget is not None else None,
        "coverage": coverage_to_dict(coverage) if coverage is not None else None,
        "operations": repo.list_operations(study.id),
    }
