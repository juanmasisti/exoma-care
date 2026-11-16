"""Dobles en memoria para probar solicitudes, pagos y cupones sin base de datos ni red."""

import copy
import itertools
from datetime import UTC, date, datetime
from typing import Any

from app.domain.entities.study_request import (
    Coupon,
    CoverageRequest,
    StudyBudget,
    StudyRequest,
)
from app.domain.interfaces.study_request_repository import DuplicateOperationError
from app.infrastructure.external_services.errors import ExternalServiceError

BUDGET_FIELDS = {
    "payment_mode",
    "insurer_external_id",
    "insurer_name",
    "coverage_percent",
    "insurer_cents",
    "patient_cents",
}
COVERAGE_FIELDS = {
    "status",
    "rejection_reason",
    "authorize_url",
    "reject_url",
    "resolved_at",
    "demands_count",
}
OPERATION_FIELDS = {"status", "amount_cents", "discount_cents", "coupon_code", "method"}


def _now() -> datetime:
    return datetime.now(UTC)


class InMemoryStudyRequestRepository:
    """Cumple el contrato de StudyRequestRepository; commit/rollback funcionan de verdad."""

    def __init__(self) -> None:
        self._ids = itertools.count(1)
        self.s: dict[str, Any] = {
            "patients": {},  # id -> {"name", "user_id"}
            "physicians": {},  # user_id -> datos
            "studies": {},
            "budgets": {},  # study_id -> dict
            "coverages": {},  # study_id -> dict
            "demands": [],
            "operations": {},  # id -> dict
            "coupons": {},  # code -> dict
        }
        self._committed = copy.deepcopy(self.s)
        self.commits = 0
        self.rollbacks = 0

    # --- datos de apoyo para los tests ---
    def add_patient(self, patient_id: int, name: str, user_id: int | None = None) -> None:
        self.s["patients"][patient_id] = {"name": name, "user_id": user_id}
        self.commit()
        self.commits -= 1

    def add_physician(self, user_id: int, name: str = "Médico DEMO") -> None:
        self.s["physicians"][user_id] = {
            "id": user_id,
            "name": name,
            "specialty": "Genética médica",
            "license_number": f"MN-DEMO-{user_id}",
        }
        self.commit()
        self.commits -= 1

    def committed(self) -> dict[str, Any]:
        """Estado confirmado: lo único que sobreviviría a una caída del proceso."""
        return self._committed

    # --- transacción ---
    def commit(self) -> None:
        self.commits += 1
        self._committed = copy.deepcopy(self.s)

    def rollback(self) -> None:
        self.rollbacks += 1
        self.s = copy.deepcopy(self._committed)

    # --- pacientes y médicos ---
    def patient_exists(self, patient_id: int) -> bool:
        return patient_id in self.s["patients"]

    def patient_id_for_user(self, user_id: int) -> int | None:
        for patient_id, data in self.s["patients"].items():
            if data["user_id"] == user_id:
                return patient_id
        return None

    def patient_full_name(self, patient_id: int) -> str | None:
        data = self.s["patients"].get(patient_id)
        return data["name"] if data else None

    def user_id_for_patient(self, patient_id: int) -> int | None:
        data = self.s["patients"].get(patient_id)
        return data["user_id"] if data else None

    def physician_exists(self, user_id: int) -> bool:
        return user_id in self.s["physicians"]

    def list_physicians(self) -> list[dict[str, Any]]:
        return list(self.s["physicians"].values())

    # --- solicitudes ---
    def create_study(self, *, patient_id, physician_id, include_secondary_findings, pathologies, genes):
        study_id = next(self._ids)
        self.s["studies"][study_id] = {
            "id": study_id,
            "patient_id": patient_id,
            "physician_id": physician_id,
            "status": "creado",
            "include_secondary_findings": include_secondary_findings,
            "created_at": _now(),
            "pathologies": tuple(pathologies),
            "genes": tuple(genes),
        }
        return self.get_study(study_id)

    def get_study(self, study_id):
        data = self.s["studies"].get(study_id)
        return StudyRequest(**data) if data else None

    def list_studies(self, *, physician_id=None, patient_id=None):
        return [
            StudyRequest(**data)
            for data in self.s["studies"].values()
            if (physician_id is None or data["physician_id"] == physician_id)
            and (patient_id is None or data["patient_id"] == patient_id)
        ]

    def transition_status(self, study_id, expected, new):
        data = self.s["studies"].get(study_id)
        if data is None or data["status"] != expected:
            return False
        data["status"] = new
        return True

    # --- presupuesto ---
    def create_budget(self, *, study_id, gene_count, base_cents, extra_genes, extra_cents,
                      total_cents, currency, issued_by_user_id):
        if study_id in self.s["budgets"]:
            raise RuntimeError("Ya existe un presupuesto para el estudio.")
        self.s["budgets"][study_id] = {
            "id": next(self._ids),
            "study_id": study_id,
            "gene_count": gene_count,
            "base_cents": base_cents,
            "extra_genes": extra_genes,
            "extra_cents": extra_cents,
            "total_cents": total_cents,
            "currency": currency,
            "issued_by_user_id": issued_by_user_id,
            "issued_at": _now(),
            "payment_mode": None,
            "insurer_external_id": None,
            "insurer_name": None,
            "coverage_percent": None,
            "insurer_cents": None,
            "patient_cents": None,
        }
        return self.get_budget(study_id)

    def get_budget(self, study_id):
        data = self.s["budgets"].get(study_id)
        return StudyBudget(**data) if data else None

    def update_budget(self, budget_id, **fields):
        unknown = set(fields) - BUDGET_FIELDS
        assert not unknown, f"campos de presupuesto no permitidos: {unknown}"
        for data in self.s["budgets"].values():
            if data["id"] == budget_id:
                data.update(fields)
                return
        raise LookupError("presupuesto inexistente")

    # --- cobertura ---
    def create_coverage_request(self, *, budget_id, study_id, external_id, insurer_external_id,
                                status, authorize_url, reject_url):
        self.s["coverages"][study_id] = {
            "id": next(self._ids),
            "budget_id": budget_id,
            "study_id": study_id,
            "external_id": external_id,
            "insurer_external_id": insurer_external_id,
            "status": status,
            "authorize_url": authorize_url,
            "reject_url": reject_url,
            "demands_count": 0,
            "created_at": _now(),
            "rejection_reason": None,
            "resolved_at": None,
        }
        return self.get_coverage_request(study_id)

    def get_coverage_request(self, study_id):
        data = self.s["coverages"].get(study_id)
        return CoverageRequest(**data) if data else None

    def update_coverage_request(self, coverage_id, **fields):
        unknown = set(fields) - COVERAGE_FIELDS
        assert not unknown, f"campos de cobertura no permitidos: {unknown}"
        for data in self.s["coverages"].values():
            if data["id"] == coverage_id:
                data.update(fields)
                return
        raise LookupError("cobertura inexistente")

    def add_coverage_demand(self, *, coverage_id, filename, size_bytes, uploaded_by_user_id):
        self.s["demands"].append(
            {
                "coverage_id": coverage_id,
                "filename": filename,
                "size_bytes": size_bytes,
                "uploaded_by_user_id": uploaded_by_user_id,
            }
        )

    # --- registro financiero ---
    def register_operation(self, *, study_id, budget_id, patient_id, op_type, status, amount_cents,
                           currency, discount_cents=0, coupon_code=None, insurer_external_id=None,
                           insurer_name=None, method=None, created_by_user_id=None):
        if any(
            op["budget_id"] == budget_id and op["type"] == op_type
            for op in self.s["operations"].values()
        ):
            raise DuplicateOperationError(op_type)
        operation_id = next(self._ids)
        self.s["operations"][operation_id] = {
            "id": operation_id,
            "study_id": study_id,
            "budget_id": budget_id,
            "patient_id": patient_id,
            "type": op_type,
            "status": status,
            "amount_cents": amount_cents,
            "discount_cents": discount_cents,
            "coupon_code": coupon_code,
            "currency": currency,
            "method": method,
            "insurer_external_id": insurer_external_id,
            "insurer_name": insurer_name,
            "created_at": _now(),
        }
        return operation_id

    def update_operation(self, operation_id, **fields):
        unknown = set(fields) - OPERATION_FIELDS
        assert not unknown, f"campos de operación no permitidos: {unknown}"
        self.s["operations"][operation_id].update(fields)

    def delete_operation(self, operation_id):
        self.s["operations"].pop(operation_id, None)

    def list_operations(self, study_id):
        return [
            {key: value for key, value in op.items() if key not in {"study_id", "budget_id", "patient_id"}}
            for op in self.s["operations"].values()
            if op["study_id"] == study_id
        ]

    # --- cupones ---
    def add_coupons(self, coupons):
        for code, percentage in coupons:
            self.s["coupons"][code] = {
                "code": code,
                "percentage": percentage,
                "status": "disponible",
                "generated_at": _now(),
                "medico_id": None,
                "patient_id": None,
                "redeemed_study_id": None,
            }

    def get_coupon(self, code):
        data = self.s["coupons"].get(code)
        return self._coupon(data) if data else None

    @staticmethod
    def _coupon(data):
        return Coupon(
            code=data["code"],
            percentage=data["percentage"],
            status=data["status"],
            generated_at=data["generated_at"],
            medico_id=data["medico_id"],
            patient_id=data["patient_id"],
        )

    def list_coupons(self, *, status=None, medico_id=None, patient_id=None):
        return [
            self._coupon(data)
            for data in self.s["coupons"].values()
            if (status is None or data["status"] == status)
            and (medico_id is None or data["medico_id"] == medico_id)
            and (patient_id is None or data["patient_id"] == patient_id)
        ]

    def assign_coupon_to_medico(self, code, medico_id):
        data = self.s["coupons"].get(code)
        if data is None or data["status"] != "disponible":
            return False
        data.update(status="medico", medico_id=medico_id)
        return True

    def assign_coupon_to_patient(self, code, medico_id, patient_id):
        data = self.s["coupons"].get(code)
        if data is None or data["status"] != "medico" or data["medico_id"] != medico_id:
            return False
        data.update(status="paciente", patient_id=patient_id)
        return True

    def claim_coupon(self, code, patient_id):
        data = self.s["coupons"].get(code)
        if data is None or data["status"] != "paciente" or data["patient_id"] != patient_id:
            return False
        data["status"] = "canjeando"
        return True

    def release_coupon(self, code, patient_id):
        data = self.s["coupons"].get(code)
        if data is None or data["status"] != "canjeando" or data["patient_id"] != patient_id:
            return False
        data["status"] = "paciente"
        return True

    def mark_coupon_used(self, code, study_id):
        data = self.s["coupons"].get(code)
        if data is None or data["status"] not in {"canjeando", "paciente"}:
            return False
        data.update(status="usado", redeemed_study_id=study_id)
        return True


class FakeGeneCatalog:
    def __init__(self) -> None:
        # Genes de prueba: ninguno pretende reflejar relaciones médicas reales.
        self.pathologies = [
            {"codigo": "FABRY", "nombre": "Enfermedad de Fabry", "genes": ["GLA"]},
            {"codigo": "POMPE", "nombre": "Enfermedad de Pompe", "genes": ["GAA"]},
            {"codigo": "TEST-A", "nombre": "Patología de prueba A", "genes": ["GENA1", "GENA2", "SHARED1"]},
            {"codigo": "TEST-B", "nombre": "Patología de prueba B", "genes": ["GENB1", "SHARED1"]},
            {"codigo": "VACIA", "nombre": "Sin genes", "genes": []},
        ]
        self.known_genes = {"GLA", "GAA", "GENA1", "GENA2", "GENB1", "SHARED1", "EXTRA1", "EXTRA2",
                            "EXTRA3", "EXTRA4", "EXTRA5", "EXTRA6", "BRCA1"}
        self.gene_lookups: list[str] = []

    async def listar_patologias(self):
        return copy.deepcopy(self.pathologies)

    async def genes_por_patologia(self, codigo):
        raise NotImplementedError

    async def genes_hallazgos_secundarios(self):
        raise NotImplementedError

    async def buscar_genes(self, prefijo, limit=20):
        self.gene_lookups.append(prefijo)
        return sorted(g for g in self.known_genes if g.startswith(prefijo.upper()))[:limit]


class FakeInsurance:
    def __init__(self) -> None:
        self.insurers = [
            {"id": "os-1", "rnos_codigo": "DEMO-001", "nombre": "Obra Social Uno", "sigla": "OSU",
             "porcentaje_cobertura": 40},
            {"id": "os-2", "rnos_codigo": "DEMO-002", "nombre": "Obra Social Dos", "sigla": None,
             "porcentaje_cobertura": 100},
        ]
        self.requests: dict[str, dict[str, Any]] = {}
        self.calls: list[tuple] = []
        self.fail: dict[str, Exception] = {}  # nombre de método -> excepción a lanzar
        self._counter = itertools.count(1)

    def _maybe_fail(self, method: str) -> None:
        if method in self.fail:
            raise self.fail[method]

    async def listar_obras_sociales(self, buscar=None):
        self.calls.append(("listar", buscar))
        return copy.deepcopy(self.insurers)

    async def obtener_obra_social(self, obra_social_id):
        return next((copy.deepcopy(i) for i in self.insurers if i["id"] == obra_social_id), None)

    async def crear_solicitud(self, *, obra_social_id, paciente_nombre, fecha: date, referencia_externa):
        self._maybe_fail("crear_solicitud")
        number = next(self._counter)
        insurer = await self.obtener_obra_social(obra_social_id)
        request = {
            "id": f"sol-{number}",
            "estado": "pendiente",
            "obra_social": {"id": obra_social_id},
            "paciente_nombre": paciente_nombre,
            "fecha": fecha.isoformat(),
            "referencia_externa": referencia_externa,
            "porcentaje_cobertura": None,
            "urls_simulacion": {
                "autorizar": f"https://obras.test/simulacion/tok{number}/autorizar",
                "rechazar": f"https://obras.test/simulacion/tok{number}/rechazar",
            },
            "_default_percent": insurer["porcentaje_cobertura"],
        }
        self.requests[request["id"]] = request
        self.calls.append(("crear_solicitud", obra_social_id, paciente_nombre, referencia_externa))
        return copy.deepcopy(request)

    def _by_url(self, url):
        return next(r for r in self.requests.values() if url in r["urls_simulacion"].values())

    async def autorizar(self, url, porcentaje=None):
        self._maybe_fail("autorizar")
        request = self._by_url(url)
        percent = porcentaje if porcentaje is not None else request["_default_percent"]
        request.update(estado="autorizada", porcentaje_cobertura=percent)
        self.calls.append(("autorizar", url, porcentaje))
        return copy.deepcopy(request)

    async def rechazar(self, url, motivo):
        self._maybe_fail("rechazar")
        request = self._by_url(url)
        request.update(estado="rechazada", motivo_rechazo=motivo)
        self.calls.append(("rechazar", url, motivo))
        return copy.deepcopy(request)

    async def presentar_demanda(self, solicitud_id, filename, content):
        self._maybe_fail("presentar_demanda")
        request = self.requests[solicitud_id]
        request["estado"] = "demanda_en_curso"
        self.calls.append(("demanda", solicitud_id, filename, len(content)))
        return copy.deepcopy(request)


class FakeCoupons:
    def __init__(self) -> None:
        self.calls: list[tuple] = []
        self.fail: dict[str, Exception] = {}
        self._counter = itertools.count(1000)
        self.redeemed: set[str] = set()

    def _maybe_fail(self, method: str) -> None:
        if method in self.fail:
            raise self.fail[method]

    async def generar_lote(self, gerente_id, cantidad, porcentaje_descuento):
        self._maybe_fail("generar_lote")
        self.calls.append(("generar_lote", gerente_id, cantidad, porcentaje_descuento))
        return [
            {"codigo_cupon": str(next(self._counter)), "porcentaje": porcentaje_descuento}
            for _ in range(cantidad)
        ]

    async def asignar_a_medico(self, gerente_id, medico_id, codigo):
        self._maybe_fail("asignar_a_medico")
        self.calls.append(("asignar_a_medico", gerente_id, medico_id, codigo))

    async def asignar_a_paciente(self, medico_id, paciente_id, codigo):
        self._maybe_fail("asignar_a_paciente")
        self.calls.append(("asignar_a_paciente", medico_id, paciente_id, codigo))

    async def canjear(self, paciente_id, codigo):
        self._maybe_fail("canjear")
        if codigo in self.redeemed:
            raise ExternalServiceError("Cupones", "El cupón ya fue usado.", 409)
        self.redeemed.add(codigo)
        self.calls.append(("canjear", paciente_id, codigo))
