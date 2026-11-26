from dataclasses import replace
from datetime import date

import pytest
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import Session, sessionmaker

from app.domain.entities.clinical_patient import PatientData
from app.domain.entities.pathology import PathologyDefinition
from app.domain.interfaces.patient_repository import PatientConflict
from app.infrastructure.database.models import Paciente, Usuario
from app.infrastructure.database.catalog_models import PathologyModel, SymptomModel
from app.infrastructure.database.patient_clinical_models import PatientClinicalRevision
from app.infrastructure.database.session import Base
from app.infrastructure.repositories.sqlalchemy_pathology_repository import SQLAlchemyPathologyRepository
from app.infrastructure.repositories.sqlalchemy_patient_repository import SQLAlchemyPatientRepository
from app.use_cases.patients import ClinicalValidationError, PatientClinicalService


@pytest.fixture
def factory(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'patients.db'}")
    event.listen(engine, "connect", lambda conn, _: conn.execute("PRAGMA foreign_keys=ON"))
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        for identifier in (1, 2):
            session.add(Usuario(id=identifier, username=f"medico{identifier}", role="treating_physician",
                first_name="Médico", last_name="Demo", phone="000", email=f"medico{identifier}@example.test", password_hash="not-a-login-credential"))
        session.add_all([SymptomModel(id=i, code=f"DEMO-{i}", label=f"Síntoma {i}", code_system="DEMO") for i in range(1,7)])
        session.flush()
        concepts = {i: session.get(SymptomModel,i) for i in range(1,7)}
        session.add_all([PathologyModel(id=1, name="Prueba A", normalized_name="prueba a", cardinal_symptom=concepts[1], secondary_symptoms=[concepts[2],concepts[3]]),
                         PathologyModel(id=2, name="Prueba B", normalized_name="prueba b", cardinal_symptom=concepts[4], secondary_symptoms=[concepts[5],concepts[6]])])
        session.commit()
    yield sessionmaker(engine, expire_on_commit=False)
    engine.dispose()


@pytest.fixture
def data():
    return PatientData("45.000.111", " Ana ", "Prueba", date(1990,1,1), "000", "ana@example.test", "Resumen de demostración", "clinical", "", (1,), (1,))


def service(session):
    return PatientClinicalService(SQLAlchemyPatientRepository(session), SQLAlchemyPathologyRepository(session))


def test_create_persists_with_pending_access_and_evidence(factory, data):
    with factory() as session:
        patient = service(session).save(data, 1, 1)
    with factory() as session:
        record = service(session).get(patient["id"], 1)
        assert record["dni"] == "45000111"
        assert record["access_status"] == "pending"
        assert record["created_by_physician_id"] == 1
        assert record["version"] == 1
        assert record["suspicions"][0]["valid"] is True
        assert record["symptoms"][0]["code_system"] == "DEMO"
        assert session.scalar(select(func.count()).select_from(Usuario)) == 2
        assert session.scalar(select(func.count()).select_from(PatientClinicalRevision)) == 1


def test_mixed_suspicions_are_rejected_without_any_patient(factory, data):
    with factory() as session:
        with pytest.raises(ClinicalValidationError) as failure:
            service(session).save(replace(data, pathology_ids=(1,2)), 1, 1)
        assert [r["valid"] for r in failure.value.results] == [True,False]
        assert session.scalar(select(func.count()).select_from(Paciente)) == 0
        assert session.scalar(select(func.count()).select_from(PatientClinicalRevision)) == 0


def test_family_patient_accepts_no_symptoms_with_recorded_history(factory, data):
    with factory() as session:
        record = service(session).save(replace(data,suspicion_type="family",family_history="Antecedente documentado ficticio", symptom_ids=(),pathology_ids=(1,2)),1,1)
        assert record["symptom_ids"] == []
        assert all(s["criterion"] == "family_history" for s in record["suspicions"])


def test_update_creates_revision_without_changing_creator(factory, data):
    with factory() as session:
        clinical = service(session)
        original = clinical.save(data,1,1)
        updated = clinical.save(replace(data,clinical_summary="Resumen actualizado",symptom_ids=(2,3)),2,None,original["id"],1)
        assert updated["version"] == 2
        assert updated["created_by_physician_id"] == 1
        history = session.scalars(select(PatientClinicalRevision).order_by(PatientClinicalRevision.version)).all()
        assert [h.changed_by_physician_id for h in history] == [1,2]
        assert history[0].snapshot["patient_data"]["clinical_summary"] == "Resumen de demostración"
        assert history[1].snapshot["patient_data"]["clinical_summary"] == "Resumen actualizado"


def test_stale_update_does_not_overwrite_newer_data(factory, data):
    with factory() as session:
        original = service(session).save(data,1,1)
    with factory() as session:
        service(session).save(replace(data,first_name="Nombre nuevo"),1,1,original["id"],1)
    with factory() as session:
        with pytest.raises(PatientConflict,match="Recargá"):
            service(session).save(replace(data,first_name="Nombre viejo"),1,1,original["id"],1)
    with factory() as session:
        assert service(session).get(original["id"],1)["first_name"] == "Nombre nuevo"
        assert session.scalar(select(func.count()).select_from(PatientClinicalRevision)) == 2


def test_duplicate_dni_is_normalized_and_shared_contact_email_is_allowed(factory, data):
    with factory() as session:
        clinical = service(session)
        clinical.save(data,1,1)
        with pytest.raises(PatientConflict,match="DNI"):
            clinical.save(replace(data,dni="45000111"),2,2)
        other = clinical.save(replace(data,dni="45000112"),1,1)
        assert other["email"] == data.email


def test_scope_parameter_limits_list_detail_and_update(factory, data):
    with factory() as session:
        clinical = service(session)
        first = clinical.save(data,1,1)
        clinical.save(replace(data,dni="45000112"),2,2)
        assert clinical.patients.list(1,"",20,0)["total"] == 1
        assert clinical.patients.list(None,"",20,0)["total"] == 2
        with pytest.raises(LookupError):
            clinical.get(first["id"],2)
        with pytest.raises(LookupError):
            clinical.save(data,2,2,first["id"],1)


@pytest.mark.parametrize("patch", [{"pathology_ids":(999,)},{"symptom_ids":(999,)},
    {"clinical_summary":" "},{"suspicion_type":"family","family_history":""}])
def test_invalid_inputs_do_not_create_records(factory, data, patch):
    with factory() as session:
        with pytest.raises(ValueError):
            service(session).save(replace(data,**patch),1,1)
        assert session.scalar(select(func.count()).select_from(Paciente)) == 0


def test_catalog_changes_do_not_rewrite_previous_patient_evidence(factory, data):
    with factory() as session:
        clinical = service(session)
        original = clinical.save(data,1,1)
        clinical.catalog.save(PathologyDefinition("Prueba A",4,frozenset({5,6})),1)
        historical = clinical.get(original["id"],1)
        assert historical["suspicions"][0]["definition"]["cardinal_symptom"]["id"] == 1
        with pytest.raises(ClinicalValidationError):
            clinical.save(data,1,1,original["id"],1)
        assert clinical.get(original["id"],1)["version"] == 1


def test_list_search_and_pagination_do_not_return_full_clinical_summary(factory, data):
    with factory() as session:
        clinical=service(session)
        clinical.save(data,1,1)
        clinical.save(replace(data,dni="45000112",first_name="Beatriz"),1,1)
        result=clinical.patients.list(1,"",1,1)
        assert result["total"]==2 and len(result["items"])==1
        assert "clinical_summary" not in result["items"][0]
        assert clinical.patients.list(1,"45.000.112",20,0)["total"]==1
        assert clinical.patients.list(1,"Beatriz",20,0)["total"]==1
        assert clinical.patients.list(1,"%",20,0)["total"]==0


def test_punctuation_only_search_does_not_match_all_dnis(factory, data):
    with factory() as session:
        clinical = service(session)
        clinical.save(data, 1, None)
        assert clinical.patients.list(None, "...", 20, 0)["total"] == 0
