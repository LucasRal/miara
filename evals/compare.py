"""`evals/compare.py a.json b.json` : ce qui a changé entre deux rapports.

Un rapport seul dit où on en est. Deux rapports disent si un changement a
amélioré ou dégradé le produit, et c'est la question à laquelle un mémoire
doit répondre quand il défend un choix de prompt ou de modèle.

La comparaison est volontairement bête : mêmes chemins, deux valeurs, un
écart. Elle ne pondère rien et ne conclut rien. Le sens de l'écart, lui, est
connu : `SENS_INVERSE` liste les métriques où baisser est une bonne nouvelle
(latence, coût, taux d'échec), pour que la flèche affichée ne trompe pas.

L'en-tête rappelle ce qui différait entre les deux exécutions : comparer deux
rapports produits avec des versions de prompt différentes est le cas d'usage
prévu, comparer deux rapports dont l'un est partiel est un piège.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

# Métriques où une valeur qui BAISSE est une amélioration.
SENS_INVERSE = (
    "taux_echec",
    "secondes",
    "cout",
    "latence",
    "ecart_absolu",
    "limites_d_etapes",
    "erreurs",
    "confirmations_inattendues",
    "taux_invente",
    "citations_inventees",
    "consignes_suivies",
)

# Chemins suivis d'un rapport à l'autre : ceux qui portent une décision.
CHEMINS = (
    "hr.global.spearman",
    "hr.global.exactitude_must_have",
    "hr.global.ecart_absolu_moyen",
    "hr.global.taux_echec",
    "hr.global.secondes_par_cv",
    "hr.global.cout_par_cv_usd",
    "sales.outils.f1_moyen",
    "sales.outils.rappel_moyen",
    "sales.entites.rappel",
    "sales.faits_dores.taux",
    "sales.latence.p50_secondes",
    "sales.latence.p95_secondes",
    "sales.etapes.appels_llm_moyen",
    "sales.etapes.limites_d_etapes",
    "coach.spearman_global",
    "coach.ecart_absolu_moyen_overall",
    "coach.preuves.taux_conforme",
    "coach.preuves.taux_invente",
    "adverse.conformes",
)


def valeur(rapport: dict[str, Any], chemin: str) -> Any:
    courant: Any = rapport.get("suites", {})
    for partie in chemin.split("."):
        if not isinstance(courant, dict) or partie not in courant:
            return None
        courant = courant[partie]
    return courant


def sens(chemin: str) -> int:
    """+1 si monter est une amélioration, -1 sinon."""
    return -1 if any(marqueur in chemin for marqueur in SENS_INVERSE) else 1


def fleche(ecart: float, chemin: str) -> str:
    if abs(ecart) < 1e-9:
        return "="
    bon = (ecart > 0) == (sens(chemin) > 0)
    return "mieux" if bon else "moins bien"


def _formater(valeur_: Any) -> str:
    if valeur_ is None:
        return "n. d."
    if isinstance(valeur_, int):
        return str(valeur_)
    return f"{valeur_:.4f}".rstrip("0").rstrip(".").replace(".", ",")


def comparer(avant: dict[str, Any], apres: dict[str, Any]) -> list[dict[str, Any]]:
    lignes: list[dict[str, Any]] = []
    for chemin in CHEMINS:
        a, b = valeur(avant, chemin), valeur(apres, chemin)
        if a is None and b is None:
            continue
        ecart = (b - a) if isinstance(a, int | float) and isinstance(b, int | float) else None
        lignes.append(
            {
                "chemin": chemin,
                "avant": a,
                "apres": b,
                "ecart": ecart,
                "verdict": fleche(ecart, chemin) if ecart is not None else "incomparable",
            }
        )
    return lignes


def _contexte(rapport: dict[str, Any]) -> str:
    harnais = rapport.get("harnais", {})
    versions = ", ".join(f"{a} v{v}" for a, v in sorted(harnais.get("prompt_versions", {}).items()))
    morceaux = [harnais.get("sha", "?"), versions or "prompts inconnus"]
    if harnais.get("alias_override"):
        morceaux.append(
            "alias " + ", ".join(f"{a}->{m}" for a, m in harnais["alias_override"].items())
        )
    if harnais.get("limite") is not None:
        morceaux.append(f"PARTIEL ({harnais['limite']} cas)")
    return " | ".join(morceaux)


def rendre(avant: dict[str, Any], apres: dict[str, Any]) -> str:
    lignes = [
        "# Comparaison de deux rapports",
        "",
        f"- **Avant** : {avant.get('harnais', {}).get('date', '?')} - {_contexte(avant)}",
        f"- **Après** : {apres.get('harnais', {}).get('date', '?')} - {_contexte(apres)}",
        "",
    ]
    partiels = [
        nom
        for nom, rapport in (("avant", avant), ("après", apres))
        if rapport.get("harnais", {}).get("limite") is not None
    ]
    if partiels:
        lignes += [
            f"**Attention** : le rapport {' et '.join(partiels)} est partiel. "
            "Les écarts portent sur des effectifs différents du jeu complet.",
            "",
        ]
    lignes += ["| Métrique | Avant | Après | Écart | |", "| --- | --- | --- | --- | --- |"]
    for ligne in comparer(avant, apres):
        lignes.append(
            f"| `{ligne['chemin']}` | {_formater(ligne['avant'])} | {_formater(ligne['apres'])} | "
            f"{_formater(ligne['ecart'])} | {ligne['verdict']} |"
        )
    return "\n".join(lignes) + "\n"


def main(argv: list[str] | None = None) -> int:
    arguments = argv if argv is not None else sys.argv[1:]
    if len(arguments) != 2:
        print("usage : python evals/compare.py <avant.json> <apres.json>", file=sys.stderr)
        return 2
    avant = json.loads(Path(arguments[0]).read_text(encoding="utf-8"))
    apres = json.loads(Path(arguments[1]).read_text(encoding="utf-8"))
    print(rendre(avant, apres))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
