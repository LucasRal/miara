"""Agent coach commercial : évaluation d'un TEXTE selon une grille explicite.

Deuxième cas d'usage commercial du mémoire. Pas d'audio (chap. 9) : le coach
lit un compte-rendu d'appel, un courriel de relance ou un script, et rend une
note par critère avec la preuve citée du texte.

Deux garde-fous portent toute la carte :
- **sortie structurée** (`CoachingFeedback`) : la grille est dans le schéma et
  le prompt, pas dans la tête du modèle — cinq critères, ni plus ni moins, et
  aucune note sans `evidence` ;
- **le texte de l'utilisateur est une DONNÉE, pas une consigne** : il est
  encadré par des délimiteurs et le prompt interdit d'exécuter ce qu'il
  contient (test d'injection de la carte).
"""

from pydantic import BaseModel, Field, field_validator

from app.core.agents.definition import AgentDefinition
from app.sales.tools import get_account_context, log_call_note

AGENT_NAME = "sales.coach"

# Grille de coaching (ancres 0/3/5 détaillées dans prompts/sales.coach/v<N>.md).
# L'ordre fait foi : il structure le retour et les moyennes de progression.
CRITERIA: tuple[str, ...] = (
    "decouverte_des_besoins",
    "gestion_des_objections",
    "proposition_de_valeur",
    "prochaine_etape",
    "ton_et_concision",
)

# Libellés lisibles (notes journalisées dans le CRM, interfaces).
LABELS: dict[str, str] = {
    "decouverte_des_besoins": "découverte des besoins",
    "gestion_des_objections": "gestion des objections",
    "proposition_de_valeur": "proposition de valeur",
    "prochaine_etape": "prochaine étape",
    "ton_et_concision": "ton et concision",
}

KINDS: tuple[str, ...] = ("call_note", "email", "script")


class CriterionScore(BaseModel):
    name: str = Field(description="Nom du critère de la grille")
    score_0_5: int = Field(ge=0, le=5, description="Note de 0 à 5 selon les ancres")
    evidence: str = Field(
        min_length=1,
        description=(
            "Preuve tirée du texte évalué : citation courte, ou mention "
            "explicite de l'absence (ex. « aucune objection traitée »)"
        ),
    )
    advice: str = Field(min_length=1, description="Conseil actionnable, une phrase")

    @field_validator("name")
    @classmethod
    def _critere_connu(cls, value: str) -> str:
        if value not in CRITERIA:
            raise ValueError(f"Critère inconnu : {value!r}. Attendus : {', '.join(CRITERIA)}")
        return value


class CoachingFeedback(BaseModel):
    """Retour structuré du coach. La grille est FERMÉE : cinq critères."""

    criteria: list[CriterionScore]
    strengths: list[str]
    improvements: list[str]
    suggested_next_step: str = Field(min_length=1)
    overall_0_100: int = Field(ge=0, le=100)

    @field_validator("criteria")
    @classmethod
    def _grille_complete(cls, value: list[CriterionScore]) -> list[CriterionScore]:
        names = [c.name for c in value]
        if sorted(names) != sorted(CRITERIA):
            raise ValueError(f"La grille attend exactement ces critères : {', '.join(CRITERIA)}")
        # Ordre de la grille, quel que soit l'ordre produit par le modèle.
        return sorted(value, key=lambda c: CRITERIA.index(c.name))

    def scores(self) -> dict[str, int]:
        return {c.name: c.score_0_5 for c in self.criteria}

    def summary_line(self) -> str:
        """Résumé d'une ligne, utilisé pour la note journalisée dans le CRM."""
        best = max(self.criteria, key=lambda c: c.score_0_5)
        worst = min(self.criteria, key=lambda c: c.score_0_5)
        head = f"Coaching Miara : {self.overall_0_100}/100"
        if best.score_0_5 == worst.score_0_5:  # grille homogène : rien à opposer
            return f"{head} — {best.score_0_5}/5 sur les cinq critères."
        return (
            f"{head} — point fort {LABELS[best.name]} ({best.score_0_5}/5), "
            f"à travailler {LABELS[worst.name]} ({worst.score_0_5}/5)."
        )


# Délimiteurs du bloc de texte à évaluer. Toute occurrence dans le texte de
# l'utilisateur est neutralisée avant insertion (voir `wrap_user_text`).
OPEN_DELIMITER = "<<<TEXTE_A_EVALUER"
CLOSE_DELIMITER = "TEXTE_A_EVALUER>>>"


def wrap_user_text(text: str, kind: str, account_context_hint: str | None = None) -> str:
    """Construit le message utilisateur : consignes hors du bloc, texte dedans.

    Le texte est une donnée non fiable : on retire toute tentative de refermer
    le bloc pour se faire passer pour une consigne de la plateforme.
    """
    safe = text.replace(OPEN_DELIMITER, "").replace(CLOSE_DELIMITER, "")
    header = f"Évalue le texte suivant (type : {kind}) selon la grille."
    if account_context_hint:
        header += f" Compte concerné : {account_context_hint}."
    return f"{header}\n{OPEN_DELIMITER}\n{safe}\n{CLOSE_DELIMITER}"


sales_coach = AgentDefinition(
    name=AGENT_NAME,
    # Évaluation nuancée avec citations : modèle fort dès le premier appel.
    model_alias="sales.synthesize",
    prompt_name=AGENT_NAME,  # prompts/sales.coach/v<N>.md
    tools=[get_account_context, log_call_note],
    output_schema=CoachingFeedback,
    max_steps=6,
)
