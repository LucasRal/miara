"""Application Celery du monolithe.

Deux files dès le départ (contrainte non négociable n°3, ADR-006) :
- `heavy` : extraction de texte, scoring LLM (lots de CV)
- `light` : sync CRM, notifications

Toute tâche métier doit être idempotente, avec une clé `job_id`.
"""

from celery import Celery
from kombu import Exchange, Queue

from app.config import settings

celery_app = Celery("miara", broker=settings.RABBITMQ_URL, backend=settings.REDIS_URL)
celery_app.conf.update(
    # Exchanges/clés explicites : sans cela les deux files se lient à
    # l'exchange par défaut avec la même clé et chaque message est dupliqué.
    task_queues=[
        Queue("heavy", Exchange("heavy"), routing_key="heavy"),
        Queue("light", Exchange("light"), routing_key="light"),
    ],
    task_default_queue="light",
    task_default_exchange="light",
    task_default_routing_key="light",
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_acks_late=True,
    timezone="UTC",
    enable_utc=True,
    # Chargé au démarrage du worker PAR NOM (pas d'import Python ici : core
    # n'importe jamais un module métier) : enregistre toutes les tables dans
    # Base.metadata pour résoudre les FK inter-modules (voir app/db_registry.py).
    imports=["app.db_registry"],
)


@celery_app.task(name="core.ping")  # type: ignore[untyped-decorator]
def ping() -> str:
    """Tâche de contrôle (vérifie broker + worker + backend de résultats)."""
    return "pong"
