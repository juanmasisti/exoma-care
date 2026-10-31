import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from test_patient_api import client, login, payload
from app.infrastructure.database.models import Paciente, Usuario
from app.infrastructure.database.catalog_models import PathologyModel, SymptomModel


def setup_family(http):
    headers=login(http)
    patient=http.post("/api/patients",headers=headers,json=payload()).json()
    return headers,patient,f"/api/patients/{patient['id']}/family"


def member(**patch):
    return {"full_name":"  Familiar   Prueba ","relationship":"mother","relationship_detail":"",
            "symptom_ids":[2,2],"diagnosis_status":"known","diagnosis_ids":[1,1],"notes":" Antecedente ficticio ",**patch}


def test_empty_family_is_optional_and_does_not_create_accounts(client):
    http,engine=client
    headers,patient,url=setup_family(http)
    result=http.get(url,headers=headers)
    assert result.status_code==200,result.text
    assert result.json()["members"]==[] and result.json()["version"]==0
    assert result.json()["familiogram_status"]=="not_configured"
    assert http.get(url+"/history",headers=headers).json()==[]
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(Usuario))==4
        assert session.scalar(select(func.count()).select_from(Paciente))==1


def test_save_read_and_edit_by_another_doctor_preserves_clinical_record(client):
    http,_=client
    headers,patient,url=setup_family(http)
    result=http.put(url,headers=headers,json={"version":0,"members":[member()]})
    assert result.status_code==200,result.text
    family=result.json()
    assert family["version"]==1
    saved=family["members"][0]
    assert saved["full_name"]=="Familiar Prueba" and saved["symptom_ids"]==[2] and saved["diagnosis_ids"]==[1]
    assert saved["symptoms"][0]["code"]=="DEMO-2"
    assert saved["diagnoses"][0]["name"]=="Prueba A"
    doctor2=login(http,2)
    assert http.get(url,headers=doctor2).json()["version"]==1
    changed=http.put(url,headers=doctor2,json={"version":1,"members":[member(full_name="Nombre actualizado")]})
    assert changed.status_code==200 and changed.json()["version"]==2
    history=http.get(url+"/history",headers=headers).json()
    assert [r["version"] for r in history]==[2,1]
    assert history[0]["changed_by_physician_id"]==2
    assert history[1]["members"][0]["full_name"]=="Familiar Prueba"
    current=http.get(f"/api/patients/{patient['id']}",headers=headers).json()
    assert current["version"]==1 and current["clinical_summary"]==patient["clinical_summary"]
    assert len(http.get(f"/api/patients/{patient['id']}/history",headers=headers).json())==1


def test_stale_family_edit_is_rejected_and_empty_list_keeps_history(client):
    http,_=client
    headers,_,url=setup_family(http)
    assert http.put(url,headers=headers,json={"version":0,"members":[member()]}).status_code==200
    assert http.put(url,headers=headers,json={"version":0,"members":[]}).status_code==409
    assert len(http.get(url,headers=headers).json()["members"])==1
    cleared=http.put(url,headers=headers,json={"version":1,"members":[]})
    assert cleared.status_code==200 and cleared.json()["members"]==[] and cleared.json()["version"]==2
    assert len(http.get(url+"/history",headers=headers).json()[1]["members"])==1


@pytest.mark.parametrize("patch",[
    {"full_name":"   "},{"relationship":"invented"},{"relationship":"other","relationship_detail":""},
    {"diagnosis_status":"known","diagnosis_ids":[]},
    {"diagnosis_status":"unknown","diagnosis_ids":[1]},
    {"diagnosis_status":"none","diagnosis_ids":[1]},
    {"diagnosis_ids":[999]}, {"symptom_ids":[999]}, {"diagnosis_status":"negative"},
    {"patient_id":123}, {"full_name":"A"*201}, {"notes":"x"*4001},
])
def test_invalid_family_never_partially_saves(client,patch):
    http,_=client
    headers,_,url=setup_family(http)
    refused=http.put(url,headers=headers,json={"version":0,"members":[member(),member(**patch)]})
    assert refused.status_code==422,refused.text
    assert http.get(url,headers=headers).json()["version"]==0
    assert http.get(url,headers=headers).json()["members"]==[]


def test_unknown_and_no_known_diagnoses_are_distinct_and_symptoms_optional(client):
    http,_=client
    headers,_,url=setup_family(http)
    members=[member(diagnosis_status="unknown",diagnosis_ids=[],symptom_ids=[]),
             member(diagnosis_status="none",diagnosis_ids=[],symptom_ids=[],relationship="other",relationship_detail="Parentesco referido")]
    result=http.put(url,headers=headers,json={"version":0,"members":members})
    assert result.status_code==200,result.text
    assert [m["diagnosis_status"] for m in result.json()["members"]]==["unknown","none"]


def test_family_evidence_is_not_reinterpreted_by_catalog_edits(client):
    http,engine=client
    headers,_,url=setup_family(http)
    assert http.put(url,headers=headers,json={"version":0,"members":[member()]}).status_code==200
    with Session(engine) as session:
        session.get(SymptomModel,2).label="Etiqueta nueva"
        session.get(PathologyModel,1).name="Patología renombrada"
        session.commit()
    assert http.get(url,headers=headers).json()["members"][0]["diagnoses"][0]["name"]=="Prueba A"
    assert http.get(url+"/history",headers=headers).json()[0]["members"][0]["symptoms"][0]["label"]=="Síntoma 2"


def test_family_requires_doctor_and_existing_patient_and_valid_payload(client):
    http,_=client
    headers,_,url=setup_family(http)
    for actor in (None,login(http,3),login(http,4)):
        for path in (url,url+"/history"):
            assert http.get(path,headers=actor).status_code==(401 if actor is None else 403)
        assert http.put(url,headers=actor,json={"version":0,"members":[]}).status_code==(401 if actor is None else 403)
    assert http.get("/api/patients/999/family",headers=headers).status_code==404
    assert http.put("/api/patients/999/family",headers=headers,json={"version":0,"members":[]}).status_code==404
    for body in ({"version":-1,"members":[]},{"version":0,"members":[member()]*51},{"version":0,"members":[],"actor_id":2}):
        assert http.put(url,headers=headers,json=body).status_code==422


def test_clinical_updates_do_not_change_family_versions(client):
    http,_=client
    headers,patient,url=setup_family(http)
    assert http.put(url,headers=headers,json={"version":0,"members":[member()]}).status_code==200
    update={**payload(),"version":1,"clinical_summary":"Edición clínica independiente"}
    assert http.put(f"/api/patients/{patient['id']}",headers=headers,json=update).status_code==200
    assert http.get(url,headers=headers).json()["version"]==1
    assert len(http.get(url+"/history",headers=headers).json())==1


def test_optimistic_lock_rejects_an_already_loaded_stale_database_record(client):
    from app.infrastructure.database.family_models import PatientFamilyRecord
    from app.infrastructure.repositories.sqlalchemy_family_repository import SQLAlchemyFamilyRepository
    from app.domain.interfaces.family_repository import FamilyConflict

    http,engine=client
    headers,patient,url=setup_family(http)
    assert http.put(url,headers=headers,json={"version":0,"members":[member()]}).status_code==200
    with Session(engine) as stale_session:
        stale_record=stale_session.get(PatientFamilyRecord,patient["id"])
        assert stale_record.version==1
        assert http.put(url,headers=headers,json={"version":1,"members":[member(full_name="Cambio ganador")]}).status_code==200
        with pytest.raises(FamilyConflict):
            SQLAlchemyFamilyRepository(stale_session).save(patient["id"],1,[],1)
    current=http.get(url,headers=headers).json()
    assert current["version"]==2 and current["members"][0]["full_name"]=="Cambio ganador"
    assert len(http.get(url+"/history",headers=headers).json())==2


def test_removing_members_deletes_current_associations_but_keeps_snapshots(client):
    from app.infrastructure.database.family_models import FamilyMemberModel, family_member_symptoms, family_member_diagnoses, PatientFamilyRevision

    http,engine=client
    headers,_,url=setup_family(http)
    assert http.put(url,headers=headers,json={"version":0,"members":[member()]}).status_code==200
    assert http.put(url,headers=headers,json={"version":1,"members":[]}).status_code==200
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(FamilyMemberModel))==0
        assert session.scalar(select(func.count()).select_from(family_member_symptoms))==0
        assert session.scalar(select(func.count()).select_from(family_member_diagnoses))==0
        assert session.scalar(select(func.count()).select_from(PatientFamilyRevision))==2
