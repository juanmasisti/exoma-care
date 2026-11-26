import asyncio
from datetime import datetime, timedelta, timezone
import jwt
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from app.infrastructure.database.session import Base
from app.infrastructure.database.catalog_models import SymptomModel
from app.use_cases.terminology import Terminology

SECRET = 'test-selection-secret-with-at-least-32-bytes'

class Provider:
    async def search(self, query, limit):
        return [{'code': '386661006', 'label': 'fiebre', 'code_system': 'SNOMED'}]


def test_import_is_canonical_and_preserves_existing_identity(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'terms.db'}")
    Base.metadata.create_all(engine)
    service = Terminology(Provider(), SECRET)
    token = asyncio.run(service.search('fiebre', 10, 7))[0]['selection_token']
    with Session(engine) as session:
        term = service.import_selection(token, 7, session)
        assert (term.code, term.label, term.code_system) == ('386661006', 'fiebre', 'SNOMED')
        term.label = 'Etiqueta histórica'
        session.commit()
        again = service.import_selection(token, 7, session)
        assert again.id == term.id and again.label == 'Etiqueta histórica'
        assert len(session.scalars(select(SymptomModel)).all()) == 1


@pytest.mark.parametrize('kind', ['tampered', 'other-user', 'expired', 'auth-token'])
def test_selection_cannot_be_forged_or_reused_by_another_user(kind):
    service = Terminology(Provider(), SECRET)
    token = asyncio.run(service.search('fiebre', 10, 7))[0]['selection_token']
    if kind == 'tampered':
        token = token[:-5] + 'abcde'
    if kind in ('expired', 'auth-token'):
        data = jwt.decode(token, SECRET, algorithms=['HS256'], audience='snomed-selection')
        if kind == 'expired':
            data['exp'] = datetime.now(timezone.utc) - timedelta(seconds=1)
        else:
            data['aud'] = 'login'
        token = jwt.encode(data, SECRET, algorithm='HS256')
    with pytest.raises(ValueError, match='selección'):
        service.import_selection(token, 8 if kind == 'other-user' else 7, None)
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.api.routes.terminology import router, get_terminology
from app.api.dependencies import get_database_session
from app.api.catalog_dependencies import get_current_user
from app.domain.entities.user import AuthenticatedUser
from app.domain.entities.roles import UserRole


def test_route_authorization_validation_and_import(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'api.db'}", connect_args={'check_same_thread': False})
    Base.metadata.create_all(engine)
    app = FastAPI(); app.include_router(router)
    app.dependency_overrides[get_terminology] = lambda: Terminology(Provider(), SECRET)
    def sessions():
        with Session(engine) as session:
            yield session
    app.dependency_overrides[get_database_session] = sessions
    with TestClient(app) as client:
        assert client.get('/api/terminology/symptoms?q=fiebre').status_code == 401
        app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(7, 'test@example.test', UserRole.PATIENT)
        assert client.get('/api/terminology/symptoms?q=fiebre').status_code == 403
        assert client.post('/api/terminology/symptoms/import', json={'selection_token': 'x'}).status_code == 403
        app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(7, 'test@example.test', UserRole.TREATING_PHYSICIAN)
        for query in ('q=ab', 'q=fiebre&limit=51'):
            assert client.get('/api/terminology/symptoms?' + query).status_code == 422
        response = client.get('/api/terminology/symptoms?q=fiebre')
        assert response.status_code == 200
        token = response.json()[0]['selection_token']
        assert client.post('/api/terminology/symptoms/import', json={'selection_token': token, 'label': 'fake'}).status_code == 422
        result = client.post('/api/terminology/symptoms/import', json={'selection_token': token})
        assert result.status_code == 200 and result.json()['label'] == 'fiebre'
        assert client.post('/api/terminology/symptoms/import', json={'selection_token': token}).json()['id'] == result.json()['id']


def test_concurrent_imports_share_one_identity(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from sqlalchemy import event
    engine = create_engine(f"sqlite:///{tmp_path / 'concurrent.db'}", connect_args={'check_same_thread': False, 'timeout': 10})
    Base.metadata.create_all(engine)
    service = Terminology(Provider(), SECRET)
    token = asyncio.run(service.search('fiebre', 10, 7))[0]['selection_token']
    barrier = Barrier(2)
    def import_term():
        with Session(engine) as session:
            # Both sessions observe absence before either inserts, exercising unique-conflict recovery.
            first = True
            def after_select(conn, cursor, statement, parameters, context, many):
                nonlocal first
                if first and statement.lstrip().upper().startswith('SELECT'):
                    first = False
                    barrier.wait(timeout=10)
            connection = session.connection()
            event.listen(connection, 'after_cursor_execute', after_select)
            return service.import_selection(token, 7, session).id
    with ThreadPoolExecutor(max_workers=2) as pool:
        ids = list(pool.map(lambda _: import_term(), range(2)))
    assert ids[0] == ids[1]
    with Session(engine) as session:
        assert len(session.scalars(select(SymptomModel)).all()) == 1
