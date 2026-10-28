from datetime import datetime, timedelta, timezone

import jwt

from app.config import get_jwt_secret
from app.domain.entities.user import AuthenticatedUser

ACCESS_TOKEN_EXPIRE_MINUTES = 30


def create_access_token(user: AuthenticatedUser) -> str:
    secret_key = get_jwt_secret()

    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user.id),
        "email": user.email,
        "role": user.role.value,
        "iat": now,
        "exp": now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, secret_key, algorithm="HS256")
