"""Agent assistant commercial — flux A du pipeline LLM ([RÉF] Pipeline LLM).

Assemblage, rien de plus : le runtime borné vient de `core`, les outils du
module `sales`, le prompt du dépôt (ADR-010), les modèles des alias (ADR-011).

Deux modèles par exécution : le 1er appel (choix des outils) part sur
`sales.route` (léger, latence), la synthèse du briefing sur `sales.synthesize`
(fort, qualité de rédaction). L'escalade est décidée par le runtime, pas par
le modèle.
"""

from app.core.agents.definition import AgentDefinition
from app.sales.tools import READ_TOOLS, WRITE_TOOLS

AGENT_NAME = "sales.assistant"

sales_assistant = AgentDefinition(
    name=AGENT_NAME,
    model_alias="sales.route",
    synthesis_alias="sales.synthesize",
    prompt_name=AGENT_NAME,  # prompts/sales.assistant/v<N>.md
    tools=[*READ_TOOLS, *WRITE_TOOLS],
    max_steps=6,
)
