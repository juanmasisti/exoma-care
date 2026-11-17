"""Casos de uso de solicitud, presupuesto, cobertura, pago y cupones (EC-10 a EC-13).

Corren con dobles en memoria: no necesitan base de datos ni red.
"""

import asyncio

import pytest
from study_request_fakes import (
    FakeCoupons,
    FakeGeneCatalog,
    FakeInsurance,
    InMemoryStudyRequestRepository,
)

from app.domain.entities.roles import UserRole
from app.domain.entities.user import AuthenticatedUser
from app.infrastructure.external_services.errors import ExternalServiceError
from app.use_cases.coupons import CouponService
from app.use_cases.study_payments import StudyPaymentService
from app.use_cases.study_request_errors import StudyRequestConflictError
from app.use_cases.study_requests import StudyRequestService

PDF = b"%PDF-1.4 contenido de prueba"


def run(coro):
    return asyncio.run(coro)


def user(user_id: int, role: UserRole) -> AuthenticatedUser:
    return AuthenticatedUser(id=user_id, email=f"u{user_id}@demo.test", role=role)


PHYSICIAN = user(10, UserRole.TREATING_PHYSICIAN)
OTHER_PHYSICIAN = user(11, UserRole.TREATING_PHYSICIAN)
ADMIN = user(20, UserRole.LAB_ADMINISTRATOR)
MANAGER = user(30, UserRole.MEDICAL_MANAGER)
PATIENT_USER = user(40, UserRole.PATIENT)
OTHER_PATIENT_USER = user(41, UserRole.PATIENT)
BIO = user(50, UserRole.BIOINFORMATICIAN)


class World:
    def __init__(self) -> None:
        self.repo = InMemoryStudyRequestRepository()
        self.repo.add_physician(PHYSICIAN.id)
        self.repo.add_physician(OTHER_PHYSICIAN.id)
        self.repo.add_patient(1, "Paciente Demo", PATIENT_USER.id)
        self.repo.add_patient(2, "Otra Paciente", OTHER_PATIENT_USER.id)
        self.genes = FakeGeneCatalog()
        self.insurance = FakeInsurance()
        self.gateway = FakeCoupons()
        self.requests = StudyRequestService(self.repo, self.genes)
        self.payments = StudyPaymentService(self.repo, self.insurance, self.gateway)
        self.coupons = CouponService(self.repo, self.gateway, "G-TEST")

    def study(self, codes=("FABRY",), extra=(), patient_id=1, physician=PHYSICIAN):
        return run(
            self.requests.crear(
                physician_id=physician.id,
                patient_id=patient_id,
                pathology_codes=codes,
                additional_genes=extra,
            )
        )

    def budgeted(self, **kwargs):
        study = self.study(**kwargs)
        self.requests.emitir_presupuesto(study["id"], ADMIN)
        return study["id"]

    def status(self, study_id):
        return self.repo.get_study(study_id).status

    def coupon_for_patient(self, percentage=20, patient_id=1, physician=PHYSICIAN):
        code = run(self.coupons.generar_lote(1, percentage))[0]["code"]
        run(self.coupons.asignar_a_medico(code, physician.id))
        run(self.coupons.asignar_a_paciente(code, physician, patient_id))
        return code


@pytest.fixture
def w():
    return World()


# ---------- EC-10: alta de la solicitud ----------


def test_catalogo_lists_pathologies_with_genes(w):
    catalog = run(w.requests.catalogo())
    fabry = next(item for item in catalog if item["code"] == "FABRY")
    assert fabry["genes"] == ["GLA"]
    assert next(item for item in catalog if item["code"] == "VACIA")["genes"] == []


def test_create_with_several_pathologies_merges_genes_without_duplicates(w):
    study = w.study(codes=("TEST-A", "TEST-B"))
    symbols = [gene["symbol"] for gene in study["genes"]]
    assert sorted(symbols) == ["GENA1", "GENA2", "GENB1", "SHARED1"]
    assert {gene["origin"] for gene in study["genes"]} == {"catalogo"}
    assert study["status"] == "creado"
    assert study["estimated_budget"]["total_cents"] == 50000


def test_create_normalizes_and_dedupes_pathology_codes(w):
    study = w.study(codes=(" fabry ", "FABRY"))
    assert [p["code"] for p in study["pathologies"]] == ["FABRY"]


def test_create_adds_manual_genes_and_ignores_those_already_in_catalog(w):
    study = w.study(codes=("FABRY",), extra=("extra1", "GLA", "EXTRA1"))
    origins = {g["symbol"]: g["origin"] for g in study["genes"]}
    assert origins == {"GLA": "catalogo", "EXTRA1": "manual"}


def test_create_rejects_unknown_manual_gene(w):
    with pytest.raises(ValueError, match="NOEXISTE"):
        w.study(extra=("noexiste",))
    assert w.repo.list_studies() == []


def test_create_rejects_unknown_pathology_unknown_patient_and_empty_selection(w):
    with pytest.raises(ValueError):
        w.study(codes=("NOPE",))
    with pytest.raises(LookupError):
        w.study(patient_id=999)
    with pytest.raises(ValueError):
        w.study(codes=())
    with pytest.raises(ValueError):
        w.study(codes=("  ",))


def test_create_rejects_study_without_any_gene(w):
    with pytest.raises(ValueError):
        w.study(codes=("VACIA",))
    assert w.repo.list_studies() == []


def test_secondary_findings_flag_is_stored(w):
    study = run(
        w.requests.crear(
            physician_id=PHYSICIAN.id,
            patient_id=1,
            pathology_codes=["FABRY"],
            include_secondary_findings=True,
        )
    )
    assert study["include_secondary_findings"] is True


# ---------- Permisos de lectura ----------


def test_read_permissions_by_role(w):
    study_id = w.study()["id"]
    for allowed in (PHYSICIAN, ADMIN, PATIENT_USER, user(1, UserRole.SUPER_ADMIN)):
        assert w.requests.obtener(study_id, allowed)["id"] == study_id
    for denied in (OTHER_PHYSICIAN, OTHER_PATIENT_USER, MANAGER, BIO):
        with pytest.raises(PermissionError):
            w.requests.obtener(study_id, denied)


def test_list_is_scoped_by_role(w):
    mine = w.study()["id"]
    w.study(physician=OTHER_PHYSICIAN, patient_id=2)
    assert [s["id"] for s in w.requests.listar(PHYSICIAN)] == [mine]
    assert [s["id"] for s in w.requests.listar(PATIENT_USER)] == [mine]
    assert len(w.requests.listar(ADMIN)) == 2
    with pytest.raises(PermissionError):
        w.requests.listar(MANAGER)


def test_missing_study_is_not_found(w):
    with pytest.raises(LookupError):
        w.requests.obtener(999, ADMIN)


# ---------- EC-11: presupuesto ----------


def test_budget_up_to_five_genes_costs_base_price(w):
    study_id = w.study(codes=("TEST-A",))["id"]  # 3 genes
    budget = w.requests.emitir_presupuesto(study_id, ADMIN)
    assert budget["total_cents"] == 50000
    assert budget["extra_genes"] == 0
    assert budget["issued_by_user_id"] == ADMIN.id


def test_budget_adds_thirty_per_extra_gene(w):
    study_id = w.study(codes=("TEST-A", "TEST-B"), extra=("EXTRA1", "EXTRA2", "EXTRA3"))["id"]
    budget = w.requests.emitir_presupuesto(study_id, ADMIN)  # 4 + 3 = 7 genes
    assert budget["gene_count"] == 7
    assert budget["extra_genes"] == 2
    assert budget["total_cents"] == 50000 + 2 * 3000


def test_budget_cannot_be_issued_twice(w):
    study_id = w.budgeted()
    with pytest.raises(StudyRequestConflictError):
        w.requests.emitir_presupuesto(study_id, ADMIN)


def test_patient_and_physician_see_the_budget_but_others_do_not(w):
    study_id = w.budgeted()
    assert w.requests.obtener_presupuesto(study_id, PATIENT_USER)["total_cents"] == 50000
    assert w.requests.obtener_presupuesto(study_id, PHYSICIAN)["total_cents"] == 50000
    with pytest.raises(PermissionError):
        w.requests.obtener_presupuesto(study_id, OTHER_PATIENT_USER)


def test_budget_view_before_issue_is_not_found(w):
    study_id = w.study()["id"]
    with pytest.raises(LookupError):
        w.requests.obtener_presupuesto(study_id, ADMIN)


# ---------- EC-13: modalidad de pago ----------


def test_particular_mode_goes_to_pending_payment(w):
    study_id = w.budgeted()
    detail = run(w.payments.elegir_modalidad(study_id, PATIENT_USER, "particular"))
    assert detail["status"] == "pendiente_pago"
    assert detail["budget"]["split"] == {"insurer_cents": 0, "patient_cents": 50000, "estimated": False}


def test_mode_requires_a_budget_and_the_owner_patient(w):
    study_id = w.study()["id"]
    with pytest.raises(StudyRequestConflictError):
        run(w.payments.elegir_modalidad(study_id, PATIENT_USER, "particular"))
    w.requests.emitir_presupuesto(study_id, ADMIN)
    for stranger in (OTHER_PATIENT_USER, PHYSICIAN, ADMIN):
        with pytest.raises(PermissionError):
            run(w.payments.elegir_modalidad(study_id, stranger, "particular"))
    with pytest.raises(ValueError):
        run(w.payments.elegir_modalidad(study_id, PATIENT_USER, "trueque"))


def test_mode_cannot_be_chosen_twice(w):
    study_id = w.budgeted()
    run(w.payments.elegir_modalidad(study_id, PATIENT_USER, "particular"))
    with pytest.raises(StudyRequestConflictError):
        run(w.payments.elegir_modalidad(study_id, PATIENT_USER, "particular"))


def test_insurance_mode_creates_external_request_and_shows_estimated_split(w):
    study_id = w.budgeted()
    detail = run(w.payments.elegir_modalidad(study_id, PATIENT_USER, "obra_social", "os-1"))
    assert detail["status"] == "pendiente_autorizacion"
    assert detail["budget"]["split"] == {"insurer_cents": 20000, "patient_cents": 30000, "estimated": True}
    assert detail["coverage"]["status"] == "pendiente"
    assert "authorize_url" not in str(detail) and "simulacion" not in str(detail)
    call = next(c for c in w.insurance.calls if c[0] == "crear_solicitud")
    assert call[2:] == ("Paciente Demo", f"estudio-{study_id}")


def test_insurance_mode_validates_insurer(w):
    study_id = w.budgeted()
    with pytest.raises(ValueError):
        run(w.payments.elegir_modalidad(study_id, PATIENT_USER, "obra_social"))
    with pytest.raises(ValueError):
        run(w.payments.elegir_modalidad(study_id, PATIENT_USER, "obra_social", "no-existe"))
    assert w.status(study_id) == "creado"


def test_insurance_api_failure_leaves_study_untouched(w):
    study_id = w.budgeted()
    w.insurance.fail["crear_solicitud"] = ExternalServiceError("Obras sociales", "caída", 503)
    with pytest.raises(ExternalServiceError):
        run(w.payments.elegir_modalidad(study_id, PATIENT_USER, "obra_social", "os-1"))
    assert w.status(study_id) == "creado"
    assert w.repo.get_coverage_request(study_id) is None


# ---------- EC-13: autorización de cobertura ----------


def covered(w, insurer="os-1"):
    study_id = w.budgeted()
    run(w.payments.elegir_modalidad(study_id, PATIENT_USER, "obra_social", insurer))
    return study_id


def test_partial_authorization_leaves_remainder_to_the_patient(w):
    study_id = covered(w)
    detail = run(w.payments.autorizar_cobertura(study_id, ADMIN))
    assert detail["status"] == "pendiente_pago"
    assert detail["budget"]["coverage_confirmed"] is True
    assert detail["budget"]["split"] == {"insurer_cents": 20000, "patient_cents": 30000, "estimated": False}
    ops = detail["operations"]
    assert [(o["type"], o["status"], o["amount_cents"]) for o in ops] == [
        ("cobertura_obra_social", "a_cobrar", 20000)
    ]


def test_full_coverage_enables_study_without_payment(w):
    study_id = covered(w, insurer="os-2")
    detail = run(w.payments.autorizar_cobertura(study_id, ADMIN))
    assert detail["status"] == "autorizado"
    assert detail["budget"]["split"]["patient_cents"] == 0


def test_authorization_can_only_happen_while_pending(w):
    study_id = covered(w)
    run(w.payments.autorizar_cobertura(study_id, ADMIN))
    with pytest.raises(StudyRequestConflictError):
        run(w.payments.autorizar_cobertura(study_id, ADMIN))


def test_authorization_api_failure_changes_nothing(w):
    study_id = covered(w)
    w.insurance.fail["autorizar"] = ExternalServiceError("Obras sociales", "caída", 503)
    with pytest.raises(ExternalServiceError):
        run(w.payments.autorizar_cobertura(study_id, ADMIN))
    assert w.status(study_id) == "pendiente_autorizacion"
    assert w.repo.list_operations(study_id) == []


def test_reject_then_demand_then_authorize_with_explicit_percentage(w):
    study_id = covered(w)
    detail = run(w.payments.rechazar_cobertura(study_id, ADMIN, "  Falta orden  "))
    assert detail["status"] == "rechazado"
    assert detail["coverage"]["rejection_reason"] == "Falta orden"

    detail = run(w.payments.presentar_demanda(study_id, PATIENT_USER, "C:\\docs\\demanda", PDF))
    assert detail["status"] == "pendiente_autorizacion"
    assert detail["coverage"]["status"] == "demanda_en_curso"
    assert detail["coverage"]["demands_count"] == 1
    assert w.repo.s["demands"][0]["filename"] == "demanda.pdf"

    with pytest.raises(ValueError):
        run(w.payments.autorizar_cobertura(study_id, ADMIN))
    detail = run(w.payments.autorizar_cobertura(study_id, ADMIN, 60))
    assert detail["status"] == "pendiente_pago"
    assert detail["budget"]["split"] == {"insurer_cents": 30000, "patient_cents": 20000, "estimated": False}


def test_rejection_requires_a_reason_and_pending_status(w):
    study_id = covered(w)
    with pytest.raises(ValueError):
        run(w.payments.rechazar_cobertura(study_id, ADMIN, "   "))
    with pytest.raises(ValueError):
        run(w.payments.rechazar_cobertura(study_id, ADMIN, "x" * 501))
    run(w.payments.rechazar_cobertura(study_id, ADMIN, "No corresponde"))
    with pytest.raises(StudyRequestConflictError):
        run(w.payments.rechazar_cobertura(study_id, ADMIN, "Otra vez"))


def test_demand_validations(w):
    study_id = covered(w)
    with pytest.raises(StudyRequestConflictError):  # todavía no fue rechazada
        run(w.payments.presentar_demanda(study_id, PATIENT_USER, "d.pdf", PDF))
    run(w.payments.rechazar_cobertura(study_id, ADMIN, "No corresponde"))
    with pytest.raises(PermissionError):
        run(w.payments.presentar_demanda(study_id, OTHER_PATIENT_USER, "d.pdf", PDF))
    with pytest.raises(ValueError):
        run(w.payments.presentar_demanda(study_id, PATIENT_USER, "d.pdf", b""))
    with pytest.raises(ValueError):
        run(w.payments.presentar_demanda(study_id, PATIENT_USER, "d.pdf", b"no soy pdf"))
    with pytest.raises(ValueError):
        run(w.payments.presentar_demanda(study_id, PATIENT_USER, "d.pdf", b"%PDF" + b"0" * (5 * 1024 * 1024)))
    assert w.status(study_id) == "rechazado"


def test_after_rejection_patient_can_switch_to_particular_but_not_to_insurance(w):
    study_id = covered(w)
    run(w.payments.rechazar_cobertura(study_id, ADMIN, "No corresponde"))
    with pytest.raises(StudyRequestConflictError):
        run(w.payments.elegir_modalidad(study_id, PATIENT_USER, "obra_social", "os-1"))
    detail = run(w.payments.elegir_modalidad(study_id, PATIENT_USER, "particular"))
    assert detail["status"] == "pendiente_pago"


# ---------- EC-13: pago ----------


def test_particular_payment_enables_the_study(w):
    study_id = w.budgeted()
    run(w.payments.elegir_modalidad(study_id, PATIENT_USER, "particular"))
    detail = run(w.payments.pagar(study_id, PATIENT_USER))
    assert detail["status"] == "pagado"
    assert [(o["type"], o["status"], o["amount_cents"]) for o in detail["operations"]] == [
        ("cobro_paciente", "registrada", 50000)
    ]


def test_cannot_pay_before_choosing_mode_or_twice(w):
    study_id = w.budgeted()
    with pytest.raises(StudyRequestConflictError):
        run(w.payments.pagar(study_id, PATIENT_USER))
    run(w.payments.elegir_modalidad(study_id, PATIENT_USER, "particular"))
    run(w.payments.pagar(study_id, PATIENT_USER))
    with pytest.raises(StudyRequestConflictError):
        run(w.payments.pagar(study_id, PATIENT_USER))
    assert len(w.repo.list_operations(study_id)) == 1


def test_only_the_owner_patient_can_pay(w):
    study_id = w.budgeted()
    run(w.payments.elegir_modalidad(study_id, PATIENT_USER, "particular"))
    for stranger in (OTHER_PATIENT_USER, ADMIN, PHYSICIAN):
        with pytest.raises(PermissionError):
            run(w.payments.pagar(study_id, stranger))


def test_partial_coverage_patient_pays_remainder_and_study_is_authorized(w):
    study_id = covered(w)
    run(w.payments.autorizar_cobertura(study_id, ADMIN))
    detail = run(w.payments.pagar(study_id, PATIENT_USER))
    assert detail["status"] == "autorizado"
    amounts = {o["type"]: o["amount_cents"] for o in detail["operations"]}
    assert amounts == {"cobertura_obra_social": 20000, "cobro_paciente": 30000}


def test_cannot_pay_while_authorization_is_pending(w):
    study_id = covered(w)
    with pytest.raises(StudyRequestConflictError):
        run(w.payments.pagar(study_id, PATIENT_USER))


def test_coupon_discounts_only_the_patient_part(w):
    study_id = covered(w)
    run(w.payments.autorizar_cobertura(study_id, ADMIN))
    code = w.coupon_for_patient(percentage=20)
    detail = run(w.payments.pagar(study_id, PATIENT_USER, code))
    payment = next(o for o in detail["operations"] if o["type"] == "cobro_paciente")
    assert payment["discount_cents"] == 6000
    assert payment["amount_cents"] == 24000
    assert payment["coupon_code"] == code
    assert w.repo.get_coupon(code).status == "usado"
    assert ("canjear", str(PATIENT_USER.id), code) in w.gateway.calls


def test_coupon_applies_to_particular_payment(w):
    study_id = w.budgeted()
    run(w.payments.elegir_modalidad(study_id, PATIENT_USER, "particular"))
    code = w.coupon_for_patient(percentage=10)
    detail = run(w.payments.pagar(study_id, PATIENT_USER, code))
    assert detail["status"] == "pagado"
    assert detail["operations"][0]["amount_cents"] == 45000


def test_coupon_must_belong_to_the_paying_patient(w):
    study_id = w.budgeted()
    run(w.payments.elegir_modalidad(study_id, PATIENT_USER, "particular"))
    foreign = w.coupon_for_patient(patient_id=2, physician=OTHER_PHYSICIAN)
    with pytest.raises(ValueError):
        run(w.payments.pagar(study_id, PATIENT_USER, foreign))
    with pytest.raises(ValueError):
        run(w.payments.pagar(study_id, PATIENT_USER, "9999999"))
    assert w.status(study_id) == "pendiente_pago"
    assert w.repo.list_operations(study_id) == []


def test_used_coupon_cannot_be_reused_on_another_study(w):
    first = w.budgeted()
    run(w.payments.elegir_modalidad(first, PATIENT_USER, "particular"))
    code = w.coupon_for_patient()
    run(w.payments.pagar(first, PATIENT_USER, code))

    second = w.budgeted()
    run(w.payments.elegir_modalidad(second, PATIENT_USER, "particular"))
    with pytest.raises(ValueError):
        run(w.payments.pagar(second, PATIENT_USER, code))
    assert w.status(second) == "pendiente_pago"


def test_concurrent_payments_with_the_same_coupon_charge_only_once(w):
    first = w.budgeted()
    second = w.budgeted()
    for study_id in (first, second):
        run(w.payments.elegir_modalidad(study_id, PATIENT_USER, "particular"))
    code = w.coupon_for_patient()

    async def both():
        return await asyncio.gather(
            w.payments.pagar(first, PATIENT_USER, code),
            w.payments.pagar(second, PATIENT_USER, code),
            return_exceptions=True,
        )

    results = run(both())
    assert sum(isinstance(r, dict) for r in results) == 1
    assert sum(isinstance(r, (ValueError, StudyRequestConflictError)) for r in results) == 1
    assert [c for c in w.gateway.calls if c[0] == "canjear"] == [("canjear", str(PATIENT_USER.id), code)]


def test_coupon_already_used_in_api_marks_it_used_and_releases_the_payment(w):
    study_id = w.budgeted()
    run(w.payments.elegir_modalidad(study_id, PATIENT_USER, "particular"))
    code = w.coupon_for_patient()
    w.gateway.fail["canjear"] = ExternalServiceError("Cupones", "Cupón ya usado.", 409)
    with pytest.raises(StudyRequestConflictError):
        run(w.payments.pagar(study_id, PATIENT_USER, code))
    assert w.repo.get_coupon(code).status == "usado"
    assert w.repo.list_operations(study_id) == []
    assert w.status(study_id) == "pendiente_pago"


def test_coupon_rejected_by_api_is_released(w):
    study_id = w.budgeted()
    run(w.payments.elegir_modalidad(study_id, PATIENT_USER, "particular"))
    code = w.coupon_for_patient()
    w.gateway.fail["canjear"] = ExternalServiceError("Cupones", "Cupón vencido.", 400)
    with pytest.raises(ValueError):
        run(w.payments.pagar(study_id, PATIENT_USER, code))
    assert w.repo.get_coupon(code).status == "paciente"
    assert w.repo.list_operations(study_id) == []


def test_unknown_coupon_outcome_keeps_everything_reserved(w):
    study_id = w.budgeted()
    run(w.payments.elegir_modalidad(study_id, PATIENT_USER, "particular"))
    code = w.coupon_for_patient()
    w.gateway.fail["canjear"] = ExternalServiceError("Cupones", "timeout", 503)
    with pytest.raises(ExternalServiceError):
        run(w.payments.pagar(study_id, PATIENT_USER, code))
    assert w.repo.get_coupon(code).status == "canjeando"
    assert w.repo.list_operations(study_id)[0]["status"] == "registrando"
    assert w.status(study_id) == "pendiente_pago"
    with pytest.raises(StudyRequestConflictError):  # no se puede pagar de nuevo
        run(w.payments.pagar(study_id, PATIENT_USER))


# ---------- EC-12: cupones ----------


def test_manager_generates_a_batch_and_mirrors_it_locally(w):
    items = run(w.coupons.generar_lote(3, 15))
    assert len(items) == 3
    assert {i["status"] for i in items} == {"disponible"}
    assert {i["percentage"] for i in items} == {15.0}
    assert w.gateway.calls[0] == ("generar_lote", "G-TEST", 3, 15)


@pytest.mark.parametrize("quantity,percent", [(0, 10), (101, 10), (1, 0), (1, 101), (1, -5)])
def test_batch_validation(w, quantity, percent):
    with pytest.raises(ValueError):
        run(w.coupons.generar_lote(quantity, percent))
    assert w.gateway.calls == []


def test_coupon_lifecycle_manager_to_physician_to_patient(w):
    code = run(w.coupons.generar_lote(1, 10))[0]["code"]
    assigned = run(w.coupons.asignar_a_medico(code, PHYSICIAN.id))
    assert (assigned["status"], assigned["physician_id"]) == ("medico", PHYSICIAN.id)
    given = run(w.coupons.asignar_a_paciente(code, PHYSICIAN, 1))
    assert (given["status"], given["patient_id"]) == ("paciente", 1)
    # La API de cupones recibe los ids de usuario de nuestra base, sin prefijos.
    assert ("asignar_a_medico", "G-TEST", str(PHYSICIAN.id), code) in w.gateway.calls
    assert ("asignar_a_paciente", str(PHYSICIAN.id), str(PATIENT_USER.id), code) in w.gateway.calls


def test_coupon_assignment_rules(w):
    code = run(w.coupons.generar_lote(1, 10))[0]["code"]
    with pytest.raises(LookupError):
        run(w.coupons.asignar_a_medico("0000", PHYSICIAN.id))
    with pytest.raises(ValueError):
        run(w.coupons.asignar_a_medico(code, 999))
    with pytest.raises(PermissionError):  # todavía no es del médico
        run(w.coupons.asignar_a_paciente(code, PHYSICIAN, 1))
    run(w.coupons.asignar_a_medico(code, PHYSICIAN.id))
    with pytest.raises(StudyRequestConflictError):
        run(w.coupons.asignar_a_medico(code, OTHER_PHYSICIAN.id))
    with pytest.raises(PermissionError):
        run(w.coupons.asignar_a_paciente(code, OTHER_PHYSICIAN, 1))
    with pytest.raises(LookupError):
        run(w.coupons.asignar_a_paciente(code, PHYSICIAN, 999))
    run(w.coupons.asignar_a_paciente(code, PHYSICIAN, 1))
    with pytest.raises(StudyRequestConflictError):
        run(w.coupons.asignar_a_paciente(code, PHYSICIAN, 2))


def test_coupon_cannot_go_to_a_patient_without_an_account(w):
    w.repo.add_patient(3, "Paciente Sin Cuenta", None)
    code = run(w.coupons.generar_lote(1, 10))[0]["code"]
    run(w.coupons.asignar_a_medico(code, PHYSICIAN.id))
    with pytest.raises(ValueError, match="cuenta"):
        run(w.coupons.asignar_a_paciente(code, PHYSICIAN, 3))
    assert w.repo.get_coupon(code).status == "medico"
    assert not [c for c in w.gateway.calls if c[0] == "asignar_a_paciente"]


def test_api_failure_does_not_change_local_coupon(w):
    code = run(w.coupons.generar_lote(1, 10))[0]["code"]
    w.gateway.fail["asignar_a_medico"] = ExternalServiceError("Cupones", "403", 403)
    with pytest.raises(ExternalServiceError):
        run(w.coupons.asignar_a_medico(code, PHYSICIAN.id))
    assert w.repo.get_coupon(code).status == "disponible"


def test_invalid_batch_from_api_is_reported_and_not_stored(w):
    async def broken(*_args):
        return [{"codigo_cupon": "1"}]

    w.gateway.generar_lote = broken
    with pytest.raises(ExternalServiceError):
        run(w.coupons.generar_lote(1, 10))
    assert w.repo.list_coupons() == []


def test_coupon_listing_is_scoped_by_role(w):
    mine = w.coupon_for_patient()
    other = run(w.coupons.generar_lote(1, 10))[0]["code"]
    run(w.coupons.asignar_a_medico(other, OTHER_PHYSICIAN.id))

    assert {c["code"] for c in w.coupons.listar(MANAGER)} == {mine, other}
    assert [c["code"] for c in w.coupons.listar(PHYSICIAN)] == [mine]
    assert [c["code"] for c in w.coupons.listar(PATIENT_USER)] == [mine]
    assert w.coupons.listar(OTHER_PATIENT_USER) == []
    assert [c["code"] for c in w.coupons.listar(MANAGER, "medico")] == [other]
    for denied in (ADMIN, BIO):
        with pytest.raises(PermissionError):
            w.coupons.listar(denied)


def test_empty_gerente_id_is_rejected(w):
    with pytest.raises(ValueError):
        CouponService(w.repo, w.gateway, "  ")
