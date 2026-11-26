from datetime import datetime, timedelta, timezone
import jwt
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.infrastructure.database.catalog_models import SymptomModel


class Terminology:
    def __init__(self, client, secret: str):
        self.client, self.secret = client, secret

    async def search(self, query: str, limit: int, user_id: int):
        results = await self.client.search(query, limit)
        now = datetime.now(timezone.utc)
        return [{**term, 'selection_token': jwt.encode({
            'sub': str(user_id), 'aud': 'snomed-selection', 'iat': now,
            'exp': now + timedelta(minutes=15), 'code': term['code'], 'label': term['label'],
        }, self.secret, algorithm='HS256')} for term in results]

    def import_selection(self, token: str, user_id: int, session: Session):
        try:
            payload = jwt.decode(token, self.secret, algorithms=['HS256'], audience='snomed-selection', options={'require': ['sub', 'aud', 'iat', 'exp', 'code', 'label']})
            if payload['sub'] != str(user_id):
                raise ValueError()
        except (jwt.InvalidTokenError, ValueError):
            raise ValueError('La selección venció o no es válida. Busca y selecciona el síntoma nuevamente.') from None
        statement = select(SymptomModel).where(SymptomModel.code_system == 'SNOMED', SymptomModel.code == payload['code'])
        existing = session.scalar(statement)
        if existing is not None:
            return existing
        term = SymptomModel(code_system='SNOMED', code=payload['code'], label=payload['label'])
        session.add(term)
        try:
            session.commit()
        except IntegrityError:
            session.rollback()
            existing = session.scalar(statement)
            if existing is None:
                raise
            return existing
        session.refresh(term)
        return term
