import json
from pathlib import Path
import pytest
from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import sessionmaker
from app.infrastructure.database.session import Base
from app.infrastructure.database.catalog_models import PathologyModel, SymptomModel
from seeders.catalog import seed_demo_pathologies
from seeders.clinical_catalog import load_catalog, prepare_catalog, signature, expected

@pytest.fixture
def factory(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'catalog.db'}")
    Base.metadata.create_all(engine)
    yield sessionmaker(engine)
    engine.dispose()

@pytest.fixture
def entries(tmp_path):
    # Fixture-only explicit choice. This does not approve a production cardinal.
    data = json.loads(Path('seeders/clinical_pathologies.json').read_text(encoding='utf8'))
    for e in data['pathologies']:
        if e['cardinal'] is None:
            e['cardinal'] = e['cardinal_candidates'][0]
    path=tmp_path/'criteria.json'
    path.write_text(json.dumps(data),encoding='utf8')
    return load_catalog(path)

def counts(factory):
    with factory() as s:
        return [s.scalar(select(func.count()).select_from(m)) for m in (PathologyModel,SymptomModel)]

def test_new_catalog_repeatable_and_shared_snomed_concepts(factory,entries):
    assert all(r['action']=='crear' for r in prepare_catalog(factory,entries=entries))
    assert counts(factory)==[0,0]
    prepare_catalog(factory,apply=True,entries=entries)
    before=counts(factory)
    assert all(r['action']=='sin_cambios' for r in prepare_catalog(factory,apply=True,entries=entries))
    assert before==counts(factory)
    with factory() as s:
        assert set(s.scalars(select(SymptomModel.code_system)))=={'SNOMED'}
        for e in entries:
            p=s.scalar(select(PathologyModel).where(PathologyModel.cdss_code==e['cdss_code']))
            assert signature(p)==expected(e,'SNOMED')

def test_upgrade_preserves_ids_and_legacy_concepts(factory,entries):
    seed_demo_pathologies(factory)
    with factory() as s:
        ids={p.name:p.id for p in s.scalars(select(PathologyModel))}
        legacy=list(s.scalars(select(SymptomModel.id)))
    assert all(r['action']=='conservar_personalizada' for r in prepare_catalog(factory,apply=True,entries=entries))
    assert all(r['action']=='actualizar_demo' for r in prepare_catalog(factory,upgrade=True,entries=entries))
    assert counts(factory)==[5,30]
    prepare_catalog(factory,upgrade=True,apply=True,entries=entries)
    with factory() as s:
        assert {p.name:p.id for p in s.scalars(select(PathologyModel))}==ids
        assert all(s.get(SymptomModel,i).code_system=='DEMO' for i in legacy)

def test_custom_criteria_and_identity_are_not_overwritten(factory,entries):
    seed_demo_pathologies(factory)
    with factory.begin() as s:
        p=s.scalar(select(PathologyModel).where(PathologyModel.name==entries[0]['name']))
        p.secondary_symptoms=[]
        p.apigen_code='CUSTOM'; p.apigen_group='grupo6'
    report=prepare_catalog(factory,upgrade=True,apply=True,entries=entries)
    assert report[0]['action']=='conservar_personalizada'
    with factory() as s:
        p=s.scalar(select(PathologyModel).where(PathologyModel.name==entries[0]['name']))
        assert p.secondary_symptoms==[] and p.apigen_code=='CUSTOM'

def test_failure_rolls_back_whole_application(factory,entries,monkeypatch):
    import seeders.clinical_catalog as module
    original=module.apply_entry
    def fail(session,p,e):
        original(session,p,e)
        if e==entries[1]: raise RuntimeError('simulated failure')
    monkeypatch.setattr(module,'apply_entry',fail)
    with pytest.raises(RuntimeError): prepare_catalog(factory,apply=True,entries=entries)
    assert counts(factory)==[0,0]

def test_no_implicit_cardinal_choice(tmp_path):
    data=json.loads(Path('seeders/clinical_pathologies.json').read_text(encoding='utf8'))
    data['pathologies'][0]['cardinal']=None
    path=tmp_path/'invalid.json'; path.write_text(json.dumps(data),encoding='utf8')
    with pytest.raises(ValueError,match='seleccionar un cardinal'): load_catalog(path)


def test_pompe_preserves_all_provider_cardinals(factory):
    from app.infrastructure.repositories.sqlalchemy_pathology_repository import SQLAlchemyPathologyRepository
    from app.domain.entities.pathology import validate_clinical_suspicion
    prepare_catalog(factory,apply=True)
    with factory() as session:
        model=session.scalar(select(PathologyModel).where(PathologyModel.cdss_code=='POMPE'))
        pathology=SQLAlchemyPathologyRepository(session).get_pathology(model.id)
        assert {t.code for t in pathology.cardinal_symptoms}=={'398152000','233873004'}
        for term in pathology.cardinal_symptoms:
            assert validate_clinical_suspicion(pathology.definition(),[term.id]).valid
