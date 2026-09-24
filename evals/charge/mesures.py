"""Grandeurs de la campagne de charge : fonctions pures, testables à la main.

Tout ce qui se calcule sans base, sans worker et sans réseau vit ici, pour que
les tableaux du chapitre 8 soient vérifiables sur de petits exemples. Les
percentiles ne sont PAS réimplémentés : ils viennent de `evals.metriques`, qui
sert déjà au harnais — deux implémentations donneraient deux p95.
"""

from __future__ import annotations

import csv
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Coûts unitaires observés le 2026-09-22 sur le jeu doré complet (rapport
# `evals/reports/20260922T125933_d793943-sale.json` : 0,012413 USD par CV noté).
# Ils ne servent QU'À la réservation de budget avant de lancer un scénario ;
# la dépense rapportée est toujours celle relue dans `llm_calls`, jamais celle-ci.
COUT_ESTIME_CV_USD = 0.0125
COUT_ESTIME_QUESTION_USD = 0.012


class BudgetDepasse(RuntimeError):
    """Le plafond de la campagne est atteint : plus rien ne doit être lancé."""


@dataclass
class Budget:
    """Plafond de dépense d'une campagne, en dollars.

    Deux usages, volontairement distincts :

    - `autorise()` avant de lancer un scénario, sur une ESTIMATION. Un scénario
      qui ne tient pas dans le reste n'est pas lancé du tout, plutôt que lancé
      puis coupé au milieu : un lot interrompu ne produit aucun chiffre
      exploitable, il coûte juste de l'argent.
    - `ajouter()` pendant et après, avec la dépense RÉELLE : celle relue dans
      `llm_calls` pour un lot RH (les appels partent des workers), celle
      rapportée par la passerelle pour un lot commercial (les appels partent
      d'ici). C'est elle qui fait foi dans le rapport.
    """

    plafond_usd: float
    depense_usd: float = 0.0

    @property
    def reste_usd(self) -> float:
        return round(self.plafond_usd - self.depense_usd, 6)

    @property
    def depasse(self) -> bool:
        return self.depense_usd >= self.plafond_usd

    def autorise(self, estimation_usd: float) -> bool:
        return self.depense_usd + estimation_usd <= self.plafond_usd

    def ajouter(self, cout_usd: float) -> None:
        """Ajoute une dépense réelle au cumul de la campagne."""
        self.depense_usd = round(self.depense_usd + cout_usd, 6)


def debit_cv_par_minute(cv_traites: int, secondes: float) -> float | None:
    """Débit d'un lot. None si la durée est nulle (rien à diviser)."""
    if secondes <= 0:
        return None
    return round(cv_traites * 60 / secondes, 2)


def moyenne(valeurs: Sequence[float]) -> float | None:
    return round(sum(valeurs) / len(valeurs), 4) if valeurs else None


def ecart_relatif(valeurs: Sequence[float]) -> float | None:
    """Étendue rapportée à la moyenne : (max - min) / moyenne.

    C'est la mesure que demande le critère « même graine, même config ->
    écarts < 10 % ». L'écart-type serait plus doux et masquerait une
    répétition aberrante isolée ; l'étendue, elle, la fait sortir.
    """
    if len(valeurs) < 2:
        return None
    moy = sum(valeurs) / len(valeurs)
    if moy == 0:
        return None
    return round((max(valeurs) - min(valeurs)) / moy, 4)


def points_aberrants(valeurs: Sequence[float], facteur: float = 3.0) -> list[int]:
    """Indices des points éloignés de plus de `facteur` écarts absolus médians.

    Cette fonction SIGNALE, elle ne retire rien : la section « NE PAS » de la
    carte interdit d'écarter un point sans le documenter. Le rapport publie la
    liste et garde les valeurs dans les moyennes ; à la relecture de décider.
    """
    if len(valeurs) < 3:
        return []
    triees = sorted(valeurs)
    milieu = len(triees) // 2
    mediane = triees[milieu] if len(triees) % 2 else (triees[milieu - 1] + triees[milieu]) / 2
    ecarts = sorted(abs(v - mediane) for v in valeurs)
    mad = ecarts[milieu] if len(ecarts) % 2 else (ecarts[milieu - 1] + ecarts[milieu]) / 2
    if mad == 0:
        return []
    return [i for i, v in enumerate(valeurs) if abs(v - mediane) > facteur * mad]


@dataclass
class Reproductibilite:
    """Verdict du critère « même graine, même config -> écarts < 10 % »."""

    grandeur: str
    configuration: str
    valeurs: list[float]
    ecart_relatif: float | None
    tolerance: float
    aberrants: list[int] = field(default_factory=list)

    @property
    def tenu(self) -> bool | None:
        if self.ecart_relatif is None:
            return None
        return self.ecart_relatif <= self.tolerance

    def en_dict(self) -> dict[str, Any]:
        return {
            "grandeur": self.grandeur,
            "configuration": self.configuration,
            "repetitions": len(self.valeurs),
            "valeurs": self.valeurs,
            "moyenne": moyenne(self.valeurs),
            "ecart_relatif": self.ecart_relatif,
            "tolerance": self.tolerance,
            "tenu": self.tenu,
            "indices_aberrants": self.aberrants,
        }


def reproductibilite(
    grandeur: str, configuration: str, valeurs: Sequence[float], tolerance: float = 0.10
) -> Reproductibilite:
    return Reproductibilite(
        grandeur=grandeur,
        configuration=configuration,
        valeurs=[round(v, 4) for v in valeurs],
        ecart_relatif=ecart_relatif(valeurs),
        tolerance=tolerance,
        aberrants=points_aberrants(valeurs),
    )


def verdict_file_light(
    p95_charge: float | None, p95_vide: float | None, facteur: float = 1.5
) -> dict[str, Any]:
    """Critère `mixed` : p95 sales pendant le lot < facteur x p95 à vide.

    Renvoie `tenu: None` quand une des deux mesures manque — un critère non
    mesuré n'est pas un critère tenu.
    """
    if p95_charge is None or p95_vide is None or p95_vide <= 0:
        return {
            "p95_charge_s": p95_charge,
            "p95_vide_s": p95_vide,
            "rapport": None,
            "facteur_max": facteur,
            "tenu": None,
        }
    rapport = round(p95_charge / p95_vide, 3)
    return {
        "p95_charge_s": p95_charge,
        "p95_vide_s": p95_vide,
        "rapport": rapport,
        "facteur_max": facteur,
        "tenu": rapport < facteur,
    }


def ecrire_csv(chemin: Path, lignes: Sequence[dict[str, Any]], colonnes: Sequence[str]) -> Path:
    """CSV brut, colonnes imposées : un tableau du mémoire se relit tel quel.

    Un fichier est écrit même sans ligne : une campagne qui n'a pas exécuté un
    scénario doit laisser un fichier vide plutôt qu'aucun fichier, sinon
    l'absence se confond avec un oubli.
    """
    chemin.parent.mkdir(parents=True, exist_ok=True)
    with chemin.open("w", encoding="utf-8", newline="") as flux:
        ecrivain = csv.DictWriter(flux, fieldnames=list(colonnes), extrasaction="ignore")
        ecrivain.writeheader()
        ecrivain.writerows(lignes)
    return chemin


def famine_file_light(
    a_vide: dict[str, Any], sous_charge: dict[str, Any], facteur: float = 5.0
) -> dict[str, Any]:
    """La file `light` est-elle affamée pendant un lot `heavy` ?

    Distinct du critère `mixed` de la carte, qui porte sur la latence de
    l'agent commercial. L'agent répond dans le processus FastAPI et ne passe
    pas par Celery : sa latence ne dit donc RIEN de l'état des files. Seule la
    sonde `core.ping`, qui emprunte réellement la file `light`, le dit.

    Une sonde sans réponse suffit à conclure à la famine : le délai dépassé
    est la mesure, pas une donnée manquante.
    """
    perdues = int(sous_charge.get("sans_reponse") or 0)
    p95_vide = a_vide.get("p95_secondes")
    p95_charge = sous_charge.get("p95_secondes")
    if perdues:
        return {
            "sondes_sans_reponse": perdues,
            "p95_vide_s": p95_vide,
            "p95_charge_s": p95_charge,
            "rapport": None,
            "facteur_max": facteur,
            "famine": True,
        }
    if p95_vide is None or p95_charge is None or p95_vide <= 0:
        return {
            "sondes_sans_reponse": perdues,
            "p95_vide_s": p95_vide,
            "p95_charge_s": p95_charge,
            "rapport": None,
            "facteur_max": facteur,
            "famine": None,
        }
    rapport = round(p95_charge / p95_vide, 3)
    return {
        "sondes_sans_reponse": perdues,
        "p95_vide_s": p95_vide,
        "p95_charge_s": p95_charge,
        "rapport": rapport,
        "facteur_max": facteur,
        "famine": rapport >= facteur,
    }
