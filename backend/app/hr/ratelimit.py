"""Limite de débit des appels LLM, par organisation (Redis).

Une campagne de 500 CV lance 1000 appels au modèle. Sans garde-fou, une seule
organisation sature le quota du fournisseur et dégrade les autres — voire
prend un 429 qui fait échouer le lot. Le compteur est une fenêtre glissante
d'une minute, partagée par tous les workers.

Le jeton est attendu, pas refusé : la tâche patiente puis repart. C'est un
choix assumé — un worker bloqué quelques secondes coûte moins cher qu'une
candidature perdue, et la concurrence du worker borne déjà le nombre
d'attentes simultanées.
"""

import time
import uuid

import redis
import structlog

from app.config import settings

logger = structlog.get_logger(__name__)

_PREFIX = "hr:llmrate:"
# Les tâches Celery sont synchrones : client Redis bloquant, pas asyncio.
_redis = redis.from_url(settings.REDIS_URL, decode_responses=True)


def _key(org_id: uuid.UUID, minute: int) -> str:
    return f"{_PREFIX}{org_id}:{minute}"


def acquire_slot(org_id: uuid.UUID, *, max_wait_seconds: float = 120.0) -> float:
    """Réserve un appel LLM pour l'organisation. Renvoie le temps attendu.

    Lève `TimeoutError` si le quota reste saturé au-delà de `max_wait_seconds`
    — un lot ne doit pas immobiliser un worker indéfiniment.
    """
    limit = settings.HR_LLM_CALLS_PER_MINUTE
    if limit <= 0:  # 0 = pas de limite (tests, environnement local)
        return 0.0
    started = time.monotonic()
    while True:
        minute = int(time.time() // 60)
        key = _key(org_id, minute)
        used = _redis.incr(key)
        if used == 1:
            # Expiration posée à la création : la fenêtre se nettoie seule.
            _redis.expire(key, 120)
        if int(used) <= limit:
            return time.monotonic() - started
        waited = time.monotonic() - started
        if waited >= max_wait_seconds:
            raise TimeoutError(
                f"Quota LLM de l'organisation saturé depuis {waited:.0f} s ({limit} appels/minute)"
            )
        # Attendre le début de la minute suivante, jamais plus.
        remaining = 60 - (time.time() % 60)
        logger.info("hr_rate_limited", org_id=str(org_id), sleep_s=round(remaining, 1))
        time.sleep(min(remaining + 0.05, max_wait_seconds - waited))


def reset(org_id: uuid.UUID) -> None:
    """Vide le compteur d'une organisation (tests, mesures de performance)."""
    for key in _redis.scan_iter(f"{_PREFIX}{org_id}:*"):
        _redis.delete(key)
