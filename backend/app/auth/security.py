"""Primitives de sécurité : hachage argon2 et JWT d'accès HS256 (ADR-003).

Le JWT d'accès (15 min) porte `sub` (user), `org` et `role`. Le claim `role`
est purement informatif côté client : l'autorisation relit TOUJOURS la
membership en base (app/auth/deps.py) — on ne fait jamais confiance au client.
"""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import settings

pwd_context = CryptContext(schemes=["argon2"])


def hash_password(password: str) -> str:
    return str(pwd_context.hash(password))


def verify_password(password: str, password_hash: str) -> bool:
    return bool(pwd_context.verify(password, password_hash))


def create_access_token(user_id: uuid.UUID, org_id: uuid.UUID | None, role: str | None) -> str:
    now = datetime.now(UTC)
    claims: dict[str, Any] = {
        "sub": str(user_id),
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=settings.ACCESS_TOKEN_TTL_MINUTES),
    }
    if org_id is not None:
        claims["org"] = str(org_id)
        claims["role"] = role
    return str(jwt.encode(claims, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM))


def decode_access_token(token: str) -> dict[str, Any] | None:
    """Retourne les claims si le token est valide et non expiré, sinon None."""
    try:
        claims: dict[str, Any] = jwt.decode(
            token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM]
        )
    except JWTError:
        return None
    if claims.get("type") != "access":
        return None
    return claims
