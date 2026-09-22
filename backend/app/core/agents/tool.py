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
# Rendu lisible d'une écriture, montré à l'humain avant confirmation (ADR-009).
# Asynchrone et contextuel : un aperçu honnête peut devoir interroger le système
# distant (chercher les homonymes d'un contact avant de le créer, par exemple).
# Il s'exécute AVANT la confirmation, donc il ne doit jamais rien écrire.
ToolPreview = Callable[[BaseModel, RequestContext], Awaitable[str]]


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    args_schema: type[BaseModel]
    is_write: bool
    handler: ToolHandler
    # Écritures uniquement : phrase de confirmation en français pour l'UI.
    preview: ToolPreview | None = None

    async def run(self, args: BaseModel, ctx: RequestContext) -> Any:
        return await self.handler(args, ctx)

    async def render_preview(self, args: BaseModel, ctx: RequestContext) -> str | None:
        return await self.preview(args, ctx) if self.preview is not None else None

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
