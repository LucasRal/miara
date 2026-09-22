"""Compteurs d'une campagne de présélection (Redis), agrégés en fin de course.

Ce que le mémoire mesure au chapitre 8 — temps par CV, part de chaque étape,
taux d'échec — se perdrait si chaque worker écrivait dans la même ligne
`screening_runs` : contention garantie sur un lot de 500 CV. Les durées et les
compteurs s'accumulent donc dans un hachage Redis par campagne, que
`rank_run` relit une fois, écrit dans `stats_json`, puis supprime.

Le coût et les jetons ne sont PAS ici : ils se relisent dans `llm_calls` par
`trace_id`, qui vaut l'identifiant de la campagne. Une seule source de vérité
par grandeur.
"""

import uuid
from typing import cast

import redis

from app.config import settings

_PREFIX = "hr:runstats:"
_TTL_SECONDS = 24 * 3600

_redis = redis.from_url(settings.REDIS_URL, decode_responses=True)


def _key(run_id: uuid.UUID) -> str:
    return f"{_PREFIX}{run_id}"


def record_step(run_id: uuid.UUID, step: str, seconds: float) -> None:
    key = _key(run_id)
    pipe = _redis.pipeline()
    pipe.hincrbyfloat(key, f"{step}_seconds", round(seconds, 3))
    pipe.hincrby(key, f"{step}_count", 1)
    pipe.expire(key, _TTL_SECONDS)
    pipe.execute()


def record_failure(run_id: uuid.UUID, step: str) -> None:
    key = _key(run_id)
    pipe = _redis.pipeline()
    pipe.hincrby(key, f"failed_{step}", 1)
    pipe.hincrby(key, "failed_total", 1)
    pipe.expire(key, _TTL_SECONDS)
    pipe.execute()


def collect(run_id: uuid.UUID) -> dict[str, float]:
    """Compteurs bruts de la campagne (vide si rien n'a été enregistré)."""
    # decode_responses=True : les clés et valeurs reviennent en str, mais les
    # stubs redis annoncent l'union avec bytes.
    raw = cast(dict[str, str], _redis.hgetall(_key(run_id)))
    return {k: float(v) for k, v in raw.items()}


def clear(run_id: uuid.UUID) -> None:
    _redis.delete(_key(run_id))
