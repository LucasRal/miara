"""Contexte d'exécution d'un agent.

`org_id`, `user_id` et `role` viennent du contexte de requête (JWT vérifié)
ou de la tâche Celery — JAMAIS des arguments produits par le LLM (contrainte
2 de l'architecture). Les outils lisent l'organisation DEPUIS ce contexte.
"""

import uuid
from dataclasses import dataclass, field


@dataclass(frozen=True)
class RequestContext:
    org_id: uuid.UUID
    user_id: uuid.UUID
    role: str
    trace_id: uuid.UUID = field(default_factory=uuid.uuid4)
    # Id de l'appel d'outil en cours d'exécution (posé par la boucle avant
    # d'exécuter un outil) : clé d'idempotence des écritures. None hors boucle.
    call_id: str | None = None
    # Conversation d'où part l'exécution : rattache `agent_traces` à l'échange
    # pour rejouer une conversation avec sa trace. None hors conversation.
    conversation_id: uuid.UUID | None = None
