"""Cache Redis court (60 s) des résultats d'outils de lecture.

Une conversation d'agent répète souvent la même lecture (le modèle re-consulte
un compte à plusieurs tours) : ce cache absorbe ces répétitions. Clé =
(org, outil, args) — jamais partagée entre organisations. Les valeurs sont le
résultat DÉJÀ sérialisable (dict/list) renvoyé par l'outil.
"""

import hashlib
import json
import uuid
from collections.abc import Awaitable, Callable
from typing import cast

import redis.asyncio as aioredis
from pydantic import BaseModel

from app.config import settings

CACHE_TTL_SECONDS = 60
_PREFIX = "sales:toolcache:"

_redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)


def _key(org_id: uuid.UUID, tool: str, args: BaseModel) -> str:
    payload = json.dumps(args.model_dump(mode="json"), sort_keys=True, ensure_ascii=False)
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
    return f"{_PREFIX}{org_id}:{tool}:{digest}"


async def cached_json[T](
    org_id: uuid.UUID,
    tool: str,
    args: BaseModel,
    producer: Callable[[], Awaitable[T]],
) -> T:
    """Renvoie le résultat mémorisé si présent, sinon exécute `producer`, le
    mémorise (60 s) et le renvoie. `producer` doit renvoyer un dict/list."""
    key = _key(org_id, tool, args)
    hit = await _redis.get(key)
    if hit is not None:
        return cast(T, json.loads(hit))
    value = await producer()
    await _redis.set(key, json.dumps(value, ensure_ascii=False, default=str), ex=CACHE_TTL_SECONDS)
    return value


async def invalidate(org_id: uuid.UUID, tool: str, args: BaseModel) -> None:
    """Supprime une entrée (mesures de latence non biaisées, tests)."""
    await _redis.delete(_key(org_id, tool, args))
