"""Refresh tokens opaques (Redis, révocables) et rate limiting du login.

Le refresh (7 j) n'est PAS un JWT : jeton aléatoire opaque stocké dans Redis
(`auth:refresh:<token>` -> {user_id, org_id}). Révoquer = supprimer la clé.
La consommation est atomique (GETDEL) : chaque refresh fait tourner le jeton,
un jeton rejoué est donc refusé.
"""

import json
import secrets
import uuid

import redis.asyncio as aioredis

from app.config import settings

_redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)

_REFRESH_PREFIX = "auth:refresh:"
_LOGIN_RL_PREFIX = "auth:login_rl:"


async def issue_refresh_token(user_id: uuid.UUID, org_id: uuid.UUID | None) -> str:
    token = secrets.token_urlsafe(32)
    payload = {"user_id": str(user_id), "org_id": str(org_id) if org_id else None}
    await _redis.set(
        _REFRESH_PREFIX + token,
        json.dumps(payload),
        ex=settings.REFRESH_TOKEN_TTL_DAYS * 86400,
    )
    return token


async def consume_refresh_token(token: str) -> dict[str, str | None] | None:
    """Consomme (rotation) : le jeton ne peut servir qu'une seule fois."""
    raw = await _redis.getdel(_REFRESH_PREFIX + token)
    if raw is None:
        return None
    data: dict[str, str | None] = json.loads(raw)
    return data


async def revoke_refresh_token(token: str) -> None:
    await _redis.delete(_REFRESH_PREFIX + token)


async def register_login_attempt(email: str, ip: str) -> bool:
    """Compte une tentative ; False si le plafond (5 / 15 min) est dépassé."""
    key = f"{_LOGIN_RL_PREFIX}{email}:{ip}"
    count = await _redis.incr(key)
    if count == 1:
        await _redis.expire(key, settings.LOGIN_WINDOW_SECONDS)
    return count <= settings.LOGIN_MAX_ATTEMPTS


async def reset_login_attempts(email: str, ip: str) -> None:
    await _redis.delete(f"{_LOGIN_RL_PREFIX}{email}:{ip}")
