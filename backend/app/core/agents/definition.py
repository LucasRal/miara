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
    # Escalade DÉTERMINISTE (ADR-011) : tant qu'il n'y a rien à exploiter, le
    # modèle léger route et choisit les outils ; dès que des résultats d'outils
    # sont en main, la synthèse part sur cet alias (fort). None = un seul modèle.
    synthesis_alias: str | None = None

    def alias_for_step(self, has_tool_results: bool) -> str:
        """Alias du prochain appel LLM. La reprise après confirmation compte
        comme « résultats en main » : la synthèse ne redescend jamais sur le
        modèle léger."""
        if self.synthesis_alias and has_tool_results:
            return self.synthesis_alias
        return self.model_alias
