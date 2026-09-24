"""Espaces de travail : « RH » et « commercial », un seul vocabulaire.

L'interface présente deux espaces dédiés plutôt qu'une barre d'onglets qui
mélange les deux métiers. Les écrans transverses — activité, file de
traitement, usage — restent uniques mais se pré-filtrent sur l'espace actif.

Ce filtrage se fait ICI, côté serveur, et non sur la page déjà rendue : ces
trois écrans sont paginés par le backend, et filtrer après coup afficherait
« page 2 sur 7 » en n'ayant réellement que trois lignes à montrer.

Ce module ne connaît que des chaînes — sources d'activité et préfixes de noms
journalisés. Aucune table, aucun modèle : chaque routeur traduit ce
vocabulaire dans sa propre requête.

`core.*` (tâches techniques, agent d'essai) et `eval.*` (harnais
d'évaluation) n'appartiennent à aucun espace : ils consomment un budget réel
et restent visibles, mais seulement quand on demande à tout voir.
"""

from typing import Final, Literal

from fastapi import HTTPException

Espace = Literal["rh", "commercial"]

ESPACES: Final[tuple[str, ...]] = ("rh", "commercial")

#: Sources du journal d'activité (clé `kind` des événements) par espace.
SOURCES: Final[dict[str, tuple[str, ...]]] = {
    "rh": ("hr_run",),
    "commercial": ("crm_write", "coaching"),
}

#: Préfixes des noms journalisés — tâches Celery (`hr.rank_run`) et agents
#: LLM (`sales.assistant`) suivent la même convention `module.fonction`.
PREFIXES: Final[dict[str, tuple[str, ...]]] = {
    "rh": ("hr.",),
    "commercial": ("sales.",),
}


def valider(espace: str | None) -> str | None:
    """Renvoie l'espace demandé, ou lève 422. `None` = tous les espaces."""
    if espace is None:
        return None
    if espace not in ESPACES:
        raise HTTPException(status_code=422, detail=f"Espace inconnu : {espace}")
    return espace


def sources(espace: str | None) -> tuple[str, ...] | None:
    """Sources d'activité de l'espace, ou `None` pour ne rien restreindre."""
    return SOURCES[espace] if espace else None


def prefixes(espace: str | None) -> tuple[str, ...] | None:
    """Préfixes de noms journalisés de l'espace, ou `None`."""
    return PREFIXES[espace] if espace else None
