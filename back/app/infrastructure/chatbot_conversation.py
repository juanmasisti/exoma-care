"""Signed, short-lived conversation handle bound to the authenticated patient."""
from datetime import datetime, timedelta, timezone
import jwt
from app.config import get_jwt_secret


def encode_conversation(cid: str, user_id: int) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode({'sub': str(user_id), 'cid': cid, 'iat': now,
                       'exp': now + timedelta(minutes=30), 'aud': 'exoma-chatbot', 'iss': 'exoma-care'},
                      get_jwt_secret(), algorithm='HS256')


def decode_conversation(token: str | None, user_id: int) -> str | None:
    if token is None:
        return None
    try:
        data = jwt.decode(token, get_jwt_secret(), algorithms=['HS256'], audience='exoma-chatbot', issuer='exoma-care',
                          options={'require': ['sub', 'cid', 'iat', 'exp', 'aud', 'iss']})
        cid = data['cid']
        if data['sub'] != str(user_id) or not isinstance(cid, str) or not cid.strip() or len(cid) > 200:
            raise ValueError()
        return cid
    except (jwt.InvalidTokenError, ValueError, TypeError):
        raise ValueError('La conversación venció o no es válida. Iniciá una nueva conversación.') from None
