"""Lecture et vérification des seuils (`evals/thresholds.yaml`).

Un harnais qui produit de jolis chiffres que personne ne regarde ne protège de
rien. Les seuils sont la partie qui FAIT ÉCHOUER une commande : `make eval`
sort en erreur dès qu'une métrique passe sous sa barre, ce qui permet de
brancher l'évaluation sur une vérification automatique avant livraison.

Un seuil porte sur un chemin pointé dans le rapport (`hr.global.spearman`).
Les seuils d'une suite non exécutée sont ignorés, jamais comptés en échec :
`--suite hr` ne doit pas échouer parce que la latence commerciale n'a pas été
mesurée. En revanche, une suite exécutée dont la métrique est absente ou non
calculable EST une violation : c'est le cas qui, sans cela, passerait inaperçu.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def lire(chemin: Path) -> list[dict[str, Any]]:
    contenu = yaml.safe_load(chemin.read_text(encoding="utf-8")) or {}
    seuils: list[dict[str, Any]] = contenu.get("seuils", [])
    for seuil in seuils:
        if "chemin" not in seuil or ("min" not in seuil and "max" not in seuil):
            raise SystemExit(f"Seuil mal formé dans {chemin} : {seuil}")
    return seuils


def valeur_au_chemin(rapport: dict[str, Any], chemin: str) -> Any:
    courant: Any = rapport
    for partie in chemin.split("."):
        if not isinstance(courant, dict) or partie not in courant:
            return None
        courant = courant[partie]
    return courant


def verifier(
    suites: dict[str, Any], seuils: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Renvoie (violations, respectés) pour les suites réellement exécutées."""
    violations: list[dict[str, Any]] = []
    respectes: list[dict[str, Any]] = []
    for seuil in seuils:
        suite = seuil["chemin"].split(".", 1)[0]
        if suite not in suites:
            continue
        valeur = valeur_au_chemin(suites, seuil["chemin"])
        ligne = {
            "chemin": seuil["chemin"],
            "valeur": valeur,
            "min": seuil.get("min"),
            "max": seuil.get("max"),
            "pourquoi": seuil.get("pourquoi"),
        }
        if valeur is None:
            violations.append({**ligne, "motif": "métrique absente ou non calculable"})
            continue
        if seuil.get("min") is not None and valeur < seuil["min"]:
            violations.append({**ligne, "motif": f"{valeur} < {seuil['min']}"})
        elif seuil.get("max") is not None and valeur > seuil["max"]:
            violations.append({**ligne, "motif": f"{valeur} > {seuil['max']}"})
        else:
            respectes.append(ligne)
    return violations, respectes
