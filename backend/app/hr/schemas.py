"""Sorties structurées du pipeline RH : profil de CV, notation contre la grille.

Deux principes portent tout ce fichier.

**Le modèle décrit, le code décide.** Le modèle note chaque critère de 0 à 5
avec une preuve citée du CV ; c'est `compute_overall` qui calcule la note
globale, par moyenne pondérée des poids de la grille, et qui applique la règle
éliminatoire. Une note globale produite par le modèle serait invérifiable,
instable d'un CV à l'autre, et impossible à auditer devant un candidat —
c'est la section NE PAS de la carte.

**Aucune note sans preuve.** `evidence` est obligatoire : soit une citation
courte du CV, soit la mention explicite de ce qui manque (`missing`). C'est ce
qui rend la présélection contestable, donc défendable.
"""

from pydantic import BaseModel, Field, field_validator

# Un CV ne peut pas obtenir la moyenne s'il rate un critère éliminatoire :
# la note est ramenée à zéro et la raison est explicite dans le retour.
MUST_HAVE_FAILED_OVERALL = 0


class Experience(BaseModel):
    title: str = Field(min_length=1, description="Intitulé du poste")
    organization: str | None = Field(default=None, description="Employeur")
    duration: str | None = Field(default=None, description="Période telle qu'écrite dans le CV")
    highlights: list[str] = Field(default_factory=list, description="Réalisations citées")


class CandidateProfile(BaseModel):
    """Structuration neutre d'un CV, indépendante de l'offre.

    Volontairement SANS jugement : cette étape ne compare rien, elle range.
    Le même profil peut ensuite servir plusieurs offres, et la séparation
    rend lisible l'origine d'une erreur — mauvaise lecture du CV, ou mauvaise
    appréciation face à la grille.
    """

    headline: str | None = Field(default=None, description="Titre ou accroche du CV")
    years_experience: float | None = Field(
        default=None, ge=0, le=60, description="Années d'expérience professionnelle estimées"
    )
    skills: list[str] = Field(default_factory=list, description="Compétences citées")
    experiences: list[Experience] = Field(default_factory=list)
    education: list[str] = Field(default_factory=list, description="Diplômes et établissements")
    languages: list[str] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    location: str | None = Field(default=None, description="Localisation mentionnée")
    # Le modèle signale ce qu'il n'a pas trouvé plutôt que de le deviner.
    notes: list[str] = Field(
        default_factory=list, description="Zones d'ombre ou incohérences relevées dans le CV"
    )


class CriterionAssessment(BaseModel):
    name: str = Field(min_length=1, description="Intitulé exact du critère de la grille")
    score_0_5: int = Field(ge=0, le=5, description="Note de 0 à 5 face au critère")
    evidence: str = Field(
        min_length=1,
        description=(
            "Preuve tirée du CV : citation courte, ou mention explicite de "
            "l'absence (ex. « aucune mention de Celery »)"
        ),
    )
    missing: str | None = Field(
        default=None, description="Ce qui manque pour atteindre la note maximale"
    )


class CandidateAssessment(BaseModel):
    """Retour du modèle pour UN CV face à UNE grille (ADR-007).

    `overall_0_100` n'est pas ici : il est calculé par `compute_overall`.
    """

    criteria: list[CriterionAssessment]
    must_have_failed: list[str] = Field(
        default_factory=list, description="Critères éliminatoires non satisfaits"
    )
    strengths: list[str] = Field(default_factory=list)
    concerns: list[str] = Field(default_factory=list)
    confidence: float = Field(
        ge=0, le=1, description="Confiance du modèle dans son appréciation, de 0 à 1"
    )

    @field_validator("criteria")
    @classmethod
    def _au_moins_un_critere(cls, value: list[CriterionAssessment]) -> list[CriterionAssessment]:
        if not value:
            raise ValueError("Aucun critère évalué")
        return value


def align_with_grid(
    assessment: CandidateAssessment, weights: dict[str, int], must_haves: list[str]
) -> tuple[list[dict[str, object]], list[str]]:
    """Recale l'appréciation sur la grille validée par le RH.

    Le modèle peut renommer, oublier ou inventer un critère : c'est la grille
    qui fait foi, pas sa réponse. Un critère de la grille absent du retour est
    compté 0 avec un motif explicite ; un critère inventé est écarté. Les
    éliminatoires sont recalculés ici, sans se fier à `must_have_failed`.
    """
    par_nom = {c.name.strip().lower(): c for c in assessment.criteria}
    lignes: list[dict[str, object]] = []
    rates: list[str] = []
    for name, weight in weights.items():
        found = par_nom.get(name.strip().lower())
        if found is None:
            lignes.append(
                {
                    "name": name,
                    "weight": weight,
                    "score_0_5": 0,
                    "evidence": "Critère non évalué par le modèle : aucune preuve trouvée.",
                    "missing": "Évaluation absente",
                }
            )
            if name in must_haves:
                rates.append(name)
            continue
        lignes.append(
            {
                "name": name,
                "weight": weight,
                "score_0_5": found.score_0_5,
                "evidence": found.evidence,
                "missing": found.missing,
            }
        )
        # Seuil d'un éliminatoire : en dessous de 2/5, le critère n'est pas tenu.
        if name in must_haves and found.score_0_5 < 2:
            rates.append(name)
    return lignes, rates


def compute_overall(lignes: list[dict[str, object]], must_have_failed: list[str]) -> int:
    """Note globale 0-100 : moyenne pondérée des notes, 0 si un éliminatoire
    est manqué. Calculée EN CODE (carte, section NE PAS)."""
    if must_have_failed:
        return MUST_HAVE_FAILED_OVERALL
    total_poids = sum(int(ligne["weight"]) for ligne in lignes)  # type: ignore[call-overload]
    if total_poids == 0:
        return 0
    points = sum(
        int(ligne["score_0_5"]) * int(ligne["weight"])  # type: ignore[call-overload]
        for ligne in lignes
    )
    return round(100 * points / (5 * total_poids))


class CalibrationEntry(BaseModel):
    candidate_id: str = Field(min_length=1, description="Identifiant fourni dans la liste")
    rationale: str = Field(min_length=1, description="Comparaison explicite à un autre candidat")


class Calibration(BaseModel):
    """Ordre révisé du top-K (option ADR-007 : passe comparative).

    Ne porte QUE l'ordre : les notes restent celles de l'évaluation
    individuelle, seule garante de l'égalité de traitement.
    """

    ordering: list[CalibrationEntry]
    unchanged: bool = Field(default=False, description="L'ordre initial est jugé correct")
