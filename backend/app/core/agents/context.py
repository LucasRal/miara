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
