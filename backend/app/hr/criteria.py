"""Grille de critères d'une offre : extraction assistée, validation humaine.

La grille est le protocole d'évaluation du cas d'usage RH (ADR-007) : extraite
UNE fois depuis le texte de l'offre, ajustée puis validée par le RH, elle est
ensuite appliquée à l'identique à chaque CV. C'est ce qui rend la présélection
reproductible et auditable (chap. 7) — et ce qui permet au RH de corriger un
biais dans la grille plutôt que dans 500 notations.

Deux garde-fous, repris de l'agent coach :
- **sortie structurée** (`Criteria`) : le format et le nombre de critères sont
  dans le schéma, pas dans la bonne volonté du modèle ;
- **le texte de l'offre est une DONNÉE** : il est encadré par des délimiteurs
  et le prompt interdit d'exécuter ce qu'il contient.
"""

import uuid

from pydantic import BaseModel, Field, field_validator

from app.core.llm import CallContext, LLMGateway, load_prompt

AGENT_NAME = "hr.criteria"
# Alias de configuration (ADR-011) : léger, sortie JSON. Jamais un nom de modèle.
MODEL_ALIAS = "hr.extract"

# Une grille trop courte ne discrimine pas, trop longue dilue les pondérations.
MIN_CRITERIA = 5
MAX_CRITERIA = 8


class Criterion(BaseModel):
    name: str = Field(min_length=2, max_length=80, description="Intitulé court du critère")
    weight_1_5: int = Field(ge=1, le=5, description="Importance relative, de 1 à 5")
    description: str = Field(
        min_length=1, description="Ce qui est attendu dans un CV pour satisfaire ce critère"
    )
    must_have: bool = Field(description="Critère éliminatoire si absent")


class Criteria(BaseModel):
    """Grille fermée : entre 5 et 8 critères, aux intitulés distincts."""

    criteria: list[Criterion]

    @field_validator("criteria")
    @classmethod
    def _taille_et_unicite(cls, value: list[Criterion]) -> list[Criterion]:
        if not MIN_CRITERIA <= len(value) <= MAX_CRITERIA:
            raise ValueError(
                f"La grille doit compter entre {MIN_CRITERIA} et {MAX_CRITERIA} critères "
                f"(reçu : {len(value)})"
            )
        seen = [c.name.strip().lower() for c in value]
        if len(set(seen)) != len(seen):
            raise ValueError("Deux critères portent le même intitulé")
        return value

    def weights(self) -> dict[str, int]:
        return {c.name: c.weight_1_5 for c in self.criteria}

    def must_haves(self) -> list[str]:
        return [c.name for c in self.criteria if c.must_have]


# Délimiteurs du bloc contenant le texte de l'offre (donnée non fiable).
OPEN_DELIMITER = "<<<OFFRE"
CLOSE_DELIMITER = "OFFRE>>>"


def wrap_job_text(title: str, description: str) -> str:
    """Message utilisateur : consigne hors du bloc, texte de l'offre dedans."""
    safe_title = title.replace(OPEN_DELIMITER, "").replace(CLOSE_DELIMITER, "")
    safe_body = description.replace(OPEN_DELIMITER, "").replace(CLOSE_DELIMITER, "")
    return (
        "Propose la grille de critères de l'offre suivante.\n"
        f"{OPEN_DELIMITER}\n"
        f"Intitulé : {safe_title}\n\n{safe_body}\n"
        f"{CLOSE_DELIMITER}"
    )


async def suggest_criteria(
    gateway: LLMGateway, *, org_id: uuid.UUID, title: str, description: str
) -> tuple[Criteria, int]:
    """Grille proposée par le modèle + version du prompt utilisée."""
    system, prompt_version = load_prompt(AGENT_NAME)
    result = await gateway.complete(
        MODEL_ALIAS,
        [
            {"role": "system", "content": system},
            {"role": "user", "content": wrap_job_text(title, description)},
        ],
        ctx=CallContext(org_id=org_id, agent=AGENT_NAME, prompt_version=prompt_version),
        response_model=Criteria,
    )
    if not isinstance(result.parsed, Criteria):  # pragma: no cover - garde de typage
        raise ValueError("La passerelle n'a pas renvoyé de grille exploitable")
    return result.parsed, prompt_version
