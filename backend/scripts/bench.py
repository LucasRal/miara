"""`make bench` : campagne de charge et mesures de performance (chapitre 8).

    make bench                                     # matrice complète de la carte
    make bench ARGS="--budget-usd 20"              # plafond de dépense
    make bench ARGS="--point hr-50:4:3"            # un seul point, 3 répétitions
    make bench ARGS="--alias-override hr.score=openai/gpt-4o-mini"
    make bench ARGS="--point mixed:8:1 --topologie unique"   # famine d'avant correction

Une campagne écrit un dossier daté sous `bench/reports/` : CSV bruts, figures
matplotlib, `env.json`, `campagne.json` et `rapport.md`. Aucune intervention
manuelle entre le lancement et le rapport.

Deux choses à savoir avant de lancer.

**Ça coûte de l'argent.** Chaque CV noté vaut deux appels au modèle, environ
0,0125 USD. `--budget-usd` est un plafond DUR : un point dont le coût estimé
ne tient pas dans le reste n'est pas lancé (il apparaît `ignore_budget` dans
le rapport), et un lot qui franchit le plafond en cours de route est
interrompu, la file purgée, le lot marqué `interrompu_budget`. Un lot
interrompu n'est jamais présenté comme terminé.

**Ça veut la machine pour soi.** La campagne démarre ses propres workers
Celery : par défaut un par file, comme les deux unités systemd du VPS
(`heavy` à la concurrence demandée, `light` à 2). `--topologie unique` remonte
un worker unique sur les deux files ; ce n'est la topologie d'aucun
déploiement, elle ne sert qu'à reproduire la famine de la file `light`
mesurée le 22 septembre 2026. Elle refuse de partir si un autre worker
consomme déjà les files : deux workers se partageraient les messages et la
concurrence mesurée ne serait plus celle annoncée. Vérifier aussi qu'aucune
évaluation (`make eval`) ne tourne en parallèle.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Annotated

import typer

from evals.charge.campagne import (
    NOMBRE_DE_QUESTIONS,
    SCENARIOS,
    Point,
    executer,
    lire_points,
    plan_complet,
    scenario_valide,
)
from evals.charge.worker import SEPAREE, TOPOLOGIES

app = typer.Typer(add_completion=False, help=__doc__)

CONCURRENCES_PAR_DEFAUT = "2,4,8"
REPETITIONS_PAR_DEFAUT = 3
GRAINE_PAR_DEFAUT = 20260922


def _surcharges(valeurs: list[str] | None) -> dict[str, str]:
    """`--alias-override hr.score=openai/gpt-4o` (répétable).

    Le nom du modèle vient de la ligne de commande, jamais du code : le dépôt
    ne connaît que des alias (ADR-011).
    """
    sortie: dict[str, str] = {}
    for valeur in valeurs or []:
        if "=" not in valeur:
            raise typer.BadParameter(f"Attendu alias=modele, reçu : {valeur!r}")
        alias, modele = valeur.split("=", 1)
        sortie[alias.strip()] = modele.strip()
    return sortie


def _plan(
    points: list[str] | None,
    scenarios: str,
    concurrences: str,
    repetitions: int,
    questions: int,
) -> list[Point]:
    if points:
        try:
            return lire_points(points, questions)
        except ValueError as exc:
            raise typer.BadParameter(str(exc)) from exc
    demandes = [s.strip() for s in scenarios.split(",") if s.strip()]
    inconnus = [s for s in demandes if not scenario_valide(s)]
    if inconnus:
        raise typer.BadParameter(f"Scénario inconnu : {', '.join(inconnus)}")
    return plan_complet(demandes, [int(c) for c in concurrences.split(",")], repetitions, questions)


@app.command()
def main(
    point: Annotated[
        list[str] | None,
        typer.Option(help="scenario:concurrence:repetitions, répétable (plan explicite)"),
    ] = None,
    scenario: Annotated[
        str, typer.Option(help="Scénarios de la matrice, séparés par des virgules")
    ] = ",".join(SCENARIOS),
    concurrence: Annotated[
        str, typer.Option(help="Valeurs de worker_concurrency, séparées par des virgules")
    ] = CONCURRENCES_PAR_DEFAUT,
    repetitions: Annotated[int, typer.Option(help="Répétitions par point")] = (
        REPETITIONS_PAR_DEFAUT
    ),
    budget_usd: Annotated[float, typer.Option(help="Plafond de dépense de la campagne")] = 5.0,
    graine: Annotated[int, typer.Option(help="Graine du corpus (ordre des CV)")] = (
        GRAINE_PAR_DEFAUT
    ),
    alias_override: Annotated[
        list[str] | None, typer.Option(help="alias=modele, répétable")
    ] = None,
    questions: Annotated[
        int, typer.Option(help="Questions du jeu doré posées par lot commercial")
    ] = NOMBRE_DE_QUESTIONS,
    topologie: Annotated[
        str,
        typer.Option(
            help=(
                "separee (un worker par file, topologie du VPS) ou unique "
                "(un seul worker sur heavy,light : sert à documenter la famine)"
            )
        ),
    ] = SEPAREE,
    out: Annotated[Path | None, typer.Option(help="Dossier racine des rapports")] = None,
    plan_seulement: Annotated[
        bool, typer.Option(help="Affiche le plan et son coût estimé, sans rien exécuter")
    ] = False,
) -> None:
    """Exécute la campagne et écrit le dossier de rapport."""
    if topologie not in TOPOLOGIES:
        typer.echo(f"Topologie inconnue : {topologie!r}, attendu {' ou '.join(TOPOLOGIES)}")
        raise typer.Exit(2)
    plan = _plan(point, scenario, concurrence, repetitions, questions)
    estimation = sum(p.estimation_usd() for p in plan)
    typer.echo(f"Plan : {len(plan)} point(s), coût estimé {estimation:.2f} USD")
    for p in plan:
        typer.echo(
            f"  - {p.configuration} répétition {p.repetition} ~ {p.estimation_usd():.2f} USD"
        )
    if estimation > budget_usd:
        typer.echo(
            f"\nLe plan complet ({estimation:.2f} USD) dépasse le plafond ({budget_usd:.2f} USD) : "
            "les points qui ne tiennent pas seront marqués `ignore_budget` dans le rapport."
        )
    if plan_seulement:
        raise typer.Exit(0)

    rapport = asyncio.run(
        executer(
            plan,
            budget_usd=budget_usd,
            graine=graine,
            surcharges=_surcharges(alias_override),
            topologie=topologie,
            racine_sortie=out,
            trace=typer.echo,
        )
    )
    typer.echo(f"\nDossier de campagne : {rapport['campagne']['dossier']}")
    typer.echo(
        f"Dépense réelle : {rapport['budget']['depense_usd']} USD "
        f"sur {rapport['budget']['plafond_usd']} autorisés"
    )
    non_executes = [j for j in rapport["campagne"]["journal"] if j["etat"] != "execute"]
    if non_executes:
        typer.echo(f"{len(non_executes)} point(s) non exécuté(s) : voir `rapport.md`")


if __name__ == "__main__":
    app()
