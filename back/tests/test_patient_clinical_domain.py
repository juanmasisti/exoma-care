from dataclasses import replace
from datetime import date, timedelta

import pytest

from app.domain.entities.clinical_patient import PatientData, evaluate_suspicions
from app.domain.interfaces.pathology_repository import Pathology, Symptom


@pytest.fixture
def data():
    return PatientData("45.000.111", " Ana ", "Prueba", date(1990, 1, 1), "000", "ANA@example.test", "Resumen clínico ficticio", "clinical", "", (1, 2), (10,))


@pytest.fixture
def pathologies():
    symptom = lambda id: Symptom(id, f"DEMO-{id}", "Síntoma", "DEMO")
    return [Pathology(1, "Una", symptom(10), (symptom(11), symptom(12))),
            Pathology(2, "Otra", symptom(20), (symptom(21), symptom(22)))]


def test_normalize_presentation_without_changing_meaning(data):
    normalized = replace(data, pathology_ids=(2, 1, 1), symptom_ids=(10, 10)).normalized()
    normalized.validate_fields()
    assert normalized.dni == "45000111"
    assert normalized.first_name == "Ana"
    assert normalized.email == "ana@example.test"
    assert normalized.pathology_ids == (1, 2)
    assert normalized.symptom_ids == (10,)


def test_mixed_clinical_suspicions_remain_individual(data, pathologies):
    results = evaluate_suspicions(data.normalized(), pathologies)
    assert [r["valid"] for r in results] == [True, False]
    assert not all(r["valid"] for r in results)


def test_all_clinical_suspicions_can_be_validated(data, pathologies):
    normalized = replace(data, symptom_ids=(10, 21, 22)).normalized()
    assert all(r["valid"] for r in evaluate_suspicions(normalized, pathologies))


def test_family_suspicion_accepts_no_symptoms_with_documented_history(data, pathologies):
    normalized = replace(data, suspicion_type="family", family_history="Antecedente familiar documentado de demostración", symptom_ids=()).normalized()
    normalized.validate_fields()
    results = evaluate_suspicions(normalized, pathologies)
    assert all(r["valid"] and r["criterion"] == "family_history" for r in results)


@pytest.mark.parametrize("change", [{"family_history": " ", "suspicion_type": "family"},
    {"birth_date": date.today() + timedelta(days=1)}, {"dni": "ABC"}, {"email": "no-email"},
    {"clinical_summary": " "}, {"pathology_ids": ()}, {"suspicion_type": "unknown"}])
def test_invalid_patient_fields_rejected(data, change):
    with pytest.raises(ValueError):
        replace(data, **change).normalized().validate_fields()
