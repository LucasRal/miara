"""Outil typé du runtime d'agent.

Les arguments produits par le LLM sont validés par `args_schema` (Pydantic)
AVANT toute exécution. Un outil d'écriture (`is_write=True`) n'est jamais
exécuté sans confirmation humaine (ADR-009) — c'est la boucle (runtime.py)
qui applique cette règle. Les schémas n'exposent JAMAIS org_id/credentials :
ils viennent du RequestContext.
"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel

from app.core.agents.context import RequestContext

ToolHandler = Callable[[BaseModel, RequestContext], Awaitable[Any]]


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    args_schema: type[BaseModel]
    is_write: bool
    handler: ToolHandler

    async def run(self, args: BaseModel, ctx: RequestContext) -> Any:
        return await self.handler(args, ctx)

    def to_llm_schema(self) -> dict[str, Any]:
        """Déclaration au format outil OpenAI (compris par litellm)."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.args_schema.model_json_schema(),
            },
        }
