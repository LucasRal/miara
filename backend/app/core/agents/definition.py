"""Définition déclarative d'un agent (voir [RÉF] Pipeline LLM).

Un seul runtime, plusieurs définitions : prompt système versionné (ADR-010),
alias de modèle (ADR-011, jamais un nom de modèle), outils typés, schéma de
sortie optionnel, boucle bornée (max_steps=6).
"""

from dataclasses import dataclass, field

from pydantic import BaseModel

from app.core.agents.tool import Tool


@dataclass(frozen=True)
class AgentDefinition:
    name: str
    model_alias: str
    prompt_name: str  # dossier dans prompts/ (ADR-010)
    tools: list[Tool] = field(default_factory=list)
    output_schema: type[BaseModel] | None = None
    max_steps: int = 6
