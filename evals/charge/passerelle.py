"""Passerelle de campagne : celle du harnais, qui tient le compteur de dépense.

Les appels RH partent des workers Celery, qui construisent leur propre
passerelle : leur coût se relit dans `llm_calls` par `trace_id`. Les appels
commerciaux, eux, partent de ce processus — le plafond de budget doit donc
pouvoir les arrêter entre deux questions, sans attendre un sondage de la base.

Le préfixe `eval.` du harnais est conservé : ces appels restent des appels
d'évaluation, ils ne doivent pas gonfler les statistiques d'usage d'un client.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from app.core.llm import CallContext, LLMResult
from evals.charge.mesures import Budget, BudgetDepasse
from evals.harnais import PasserelleEval


class PasserelleComptee(PasserelleEval):
    """Refuse de partir si le plafond est atteint, et cumule la dépense réelle."""

    def __init__(self, config: dict[str, Any], budget: Budget) -> None:
        super().__init__(config=config)
        self.budget = budget

    async def complete(
        self,
        alias: str,
        messages: Any,
        *,
        ctx: CallContext,
        tools: list[dict[str, Any]] | None = None,
        response_model: type[BaseModel] | None = None,
    ) -> LLMResult:
        if self.budget.depasse:
            raise BudgetDepasse(
                f"Plafond de campagne atteint ({self.budget.plafond_usd} USD) : appel refusé"
            )
        resultat = await super().complete(
            alias, messages, ctx=ctx, tools=tools, response_model=response_model
        )
        if resultat.cost_usd is not None:
            self.budget.ajouter(float(resultat.cost_usd))
        return resultat
