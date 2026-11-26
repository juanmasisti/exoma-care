from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import Session

from app.api.dependencies import get_database_session
from app.infrastructure.database.models import Paciente, Usuario
from app.infrastructure.database.catalog_models import PathologyModel, SymptomModel
from app.infrastructure.database.security import hash_password
from app.infrastructure.database.session import Base
from app.main import app

TEST_HASH = hash_password("patient-api-test-password")


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("JWT_SECRET_KEY", "patient-api-test-secret-at-least-32-bytes")
    engine = create_engine(f"sqlite:///{tmp_path / 'api-patients.db'}", connect_args={"check_same_thread": False})
    event.listen(engine,"connect",lambda conn,_:conn.execute("PRAGMA foreign_keys=ON"))
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        for identifier, role in enumerate(["treating_physician","treating_physician","medical_manager","patient"],1):
            session.add(Usuario(id=identifier,username=f"demo{identifier}",role=role,first_name="Demo",last_name="Prueba",phone="000",email=f"demo{identifier}@example.test",password_hash=TEST_HASH))
        session.add_all([SymptomModel(id=i,code=f"DEMO-{i}",label=f"Síntoma {i}",code_system="DEMO") for i in range(1,7)])
        session.flush()
        session.add_all([PathologyModel(id=1,name="Prueba A",normalized_name="prueba a",cardinal_symptom_id=1,secondary_symptoms=[session.get(SymptomModel,2),session.get(SymptomModel,3)]),
                         PathologyModel(id=2,name="Prueba B",normalized_name="prueba b",cardinal_symptom_id=4,secondary_symptoms=[session.get(SymptomModel,5),session.get(SymptomModel,6)])])
        session.commit()
    def database_session():
        with Session(engine) as session:
            yield session
    app.dependency_overrides[get_database_session]=database_session
    try:
        with TestClient(app) as http:
            yield http,engine
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def login(http,identifier=1):
    result=http.post("/api/auth/login",json={"email":f"demo{identifier}@example.test","password":"patient-api-test-password"})
    assert result.status_code==200
    return {"Authorization":"Bearer "+result.json()["access_token"]}


def payload():
    return {"dni":"45.000.111","first_name":" Ana ","last_name":"Prueba","birth_date":"1990-01-01","phone":"000", "email":"ana@example.test","clinical_summary":"Resumen ficticio", "suspicion_type":"clinical","family_history":"","pathology_ids":[1],"symptom_ids":[1]}


def test_real_login_create_global_read_update_history_and_stale_edit(client):
    http,_=client
    doctor1,doctor2=login(http),login(http,2)
    response=http.post("/api/patients",headers=doctor1,json=payload())
    assert response.status_code==201,response.text
    patient=response.json()
    assert patient["dni"]=="45000111" and patient["first_name"]=="Ana"
    assert patient["access_status"]=="pending" and patient["version"]==1
    identifier=patient["id"]
    listed=http.get("/api/patients",headers=doctor2).json()
    assert listed["total"]==1 and listed["items"][0]["id"]==identifier
    assert "clinical_summary" not in listed["items"][0]
    assert http.get(f"/api/patients/{identifier}",headers=doctor2).status_code==200
    update={**payload(),"version":1,"clinical_summary":"Resumen actualizado por otro médico"}
    changed=http.put(f"/api/patients/{identifier}",headers=doctor2,json=update)
    assert changed.status_code==200,changed.text
    assert changed.json()["version"]==2 and changed.json()["created_by_physician_id"]==1
    assert http.put(f"/api/patients/{identifier}",headers=doctor1,json=update).status_code==409
    history=http.get(f"/api/patients/{identifier}/history",headers=doctor1).json()
    assert [r["version"] for r in history]==[2,1]
    assert history[0]["changed_by_physician_id"]==2
    assert history[1]["snapshot"]["patient_data"]["clinical_summary"]=="Resumen ficticio"


def test_preview_and_invalid_multiple_selection_do_not_persist(client):
    http,engine=client
    headers=login(http)
    invalid={**payload(),"pathology_ids":[1,2]}
    preview=http.post("/api/patients/validate",headers=headers,json=invalid)
    assert preview.status_code==200
    assert preview.json()["valid"] is False
    assert [r["valid"] for r in preview.json()["results"]]==[True,False]
    refused=http.post("/api/patients",headers=headers,json=invalid)
    assert refused.status_code==422
    assert refused.json()["detail"]["results"][1]["criterion"]=="insufficient_symptoms"
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(Paciente))==0
        assert session.scalar(select(func.count()).select_from(Usuario))==4


def test_family_with_history_and_no_symptoms_is_accepted(client):
    http,_=client
    headers=login(http)
    body={**payload(),"suspicion_type":"family","family_history":"Antecedente documentado de demostración", "symptom_ids":[],"pathology_ids":[1,2]}
    result=http.post("/api/patients",headers=headers,json=body)
    assert result.status_code==201,result.text
    assert all(r["criterion"]=="family_history" for r in result.json()["suspicions"])


@pytest.mark.parametrize("patch", [{"birth_date":(date.today()+timedelta(days=1)).isoformat()},
    {"email":"invalido"},{"clinical_summary":" "},{"pathology_ids":[]},{"pathology_ids":[999]},
    {"symptom_ids":[999]},{"suspicion_type":"family","family_history":""},
    {"created_by_physician_id":2},{"first_name":" "}])
def test_invalid_or_forged_fields_are_rejected(client,patch):
    http,engine=client
    assert http.post("/api/patients",headers=login(http),json={**payload(),**patch}).status_code==422
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(Paciente))==0


def test_dni_conflict_and_pagination_validation(client):
    http,_=client
    headers=login(http)
    assert http.post("/api/patients",headers=headers,json=payload()).status_code==201
    assert http.post("/api/patients",headers=headers,json={**payload(),"dni":"45000111"}).status_code==409
    assert http.get("/api/patients?q=45.000.111",headers=headers).json()["total"]==1
    assert http.get("/api/patients?q=Ausente",headers=headers).json()["total"]==0
    assert http.get("/api/patients?limit=101",headers=headers).status_code==422
    assert http.get("/api/patients?offset=-1",headers=headers).status_code==422
    assert http.get("/api/patients/999",headers=headers).status_code==404


def test_patient_data_is_not_available_to_manager_patient_or_anonymous(client):
    http,_=client
    assert http.get("/api/patients").status_code==401
    patient=http.post("/api/patients",headers=login(http),json=payload()).json()
    for identifier in (3,4):
        headers=login(http,identifier)
        assert http.get("/api/patients",headers=headers).status_code==403
        assert http.get(f"/api/patients/{patient['id']}",headers=headers).status_code==403
        assert http.get(f"/api/patients/{patient['id']}/history",headers=headers).status_code==403
        assert http.post("/api/patients",headers=headers,json=payload()).status_code==403
