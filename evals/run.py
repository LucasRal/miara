"""`make eval` : rejoue le jeu doré et écrit un rapport daté et comparable.

    make eval                                  # les quatre suites
    make eval ARGS="--suite hr --limit 5"      # une suite, cinq CV par offre
    make eval-verifier RAPPORT=evals/reports/<fichier>.json
    make eval-relire RAPPORT=evals/reports/<fichier>.json

Le rapport JSON est la seule sortie qui compte : il contient les chiffres, le
détail question par question et CV par CV, la configuration exacte (versions de
prompt, alias, surcharges, empreinte git) et le verdict des seuils. Un résumé
markdown est écrit à côté pour la lecture humaine, et une feuille de relecture
pour les verdicts du juge.

La commande sort en ERREUR si un seuil de `evals/thresholds.yaml` n'est pas
tenu : c'est ce qui permet de brancher l'évaluation avant une livraison.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Annotated, Any

import typer

from evals import SEUILS
from evals.harnais import (
    chemin_rapport,
    nouvelle_execution,
    passerelle,
    preparer_organisation,
)
from evals.juge import Jugement, depouiller_feuille, ecrire_feuille
from evals.resume import VERSION_RAPPORT, ecrire_resume
from evals.seuils import lire as lire_seuils
from evals.seuils import verifier
from evals.suites import adverse as suite_adverse
from evals.suites import coach as suite_coach
from evals.suites import hr as suite_hr
from evals.suites import sales as suite_sales
from evals.versions import prompts_epingles, versions_utilisees

SUITES = ("hr", "sales", "coach", "adverse")
AGENTS = ("hr.profile", "hr.score", "sales.assistant", "sales.coach")

app = typer.Typer(add_completion=False, help=__doc__)


def _surcharges(valeurs: list[str] | None) -> dict[str, str]:
    """`--alias-override hr.score=openai/gpt-4o` (répétable)."""
    sortie: dict[str, str] = {}
    for valeur in valeurs or []:
        if "=" not in valeur:
            raise typer.BadParameter(f"Attendu alias=modele, reçu : {valeur!r}")
        alias, modele = valeur.split("=", 1)
        sortie[alias.strip()] = modele.strip()
    return sortie


def _epinglages(valeurs: list[str] | None) -> dict[str, int]:
    """`--prompt-version hr.score=1` (répétable)."""
    sortie: dict[str, int] = {}
    for valeur in valeurs or []:
        if "=" not in valeur:
            raise typer.BadParameter(f"Attendu agent=version, reçu : {valeur!r}")
        agent, version = valeur.split("=", 1)
        sortie[agent.strip()] = int(version)
    return sortie


@app.command("executer")
def executer(
    suite: Annotated[str, typer.Option(help="hr | sales | coach | adverse | all")] = "all",
    limit: Annotated[
        int | None, typer.Option(help="Nombre de cas par offre / par suite (débogage)")
    ] = None,
    concurrence: Annotated[int, typer.Option(help="CV traités en parallèle")] = 6,
    prompt_version: Annotated[
        list[str] | None, typer.Option(help="agent=version, répétable")
    ] = None,
    alias_override: Annotated[
        list[str] | None, typer.Option(help="alias=modele, répétable")
    ] = None,
    out: Annotated[Path | None, typer.Option(help="Chemin du rapport JSON")] = None,
    thresholds: Annotated[Path | None, typer.Option(help="Fichier de seuils")] = None,
    live: Annotated[bool, typer.Option(help="CRM réel au lieu de FakeCRM")] = False,
) -> None:
    """Rejoue les suites demandées et écrit le rapport."""
    demandees = list(SUITES) if suite == "all" else [s.strip() for s in suite.split(",")]
    inconnues = [s for s in demandees if s not in SUITES]
    if inconnues:
        raise typer.BadParameter(f"Suite inconnue : {', '.join(inconnues)}")

    code = asyncio.run(
        _executer(
            demandees,
            limit,
            concurrence,
            _epinglages(prompt_version),
            _surcharges(alias_override),
            out,
            thresholds or SEUILS,
            live,
        )
    )
    raise typer.Exit(code)


async def _executer(
    demandees: list[str],
    limite: int | None,
    concurrence: int,
    epinglages: dict[str, int],
    surcharges: dict[str, str],
    destination: Path | None,
    fichier_seuils: Path,
    live: bool,
) -> int:
    await preparer_organisation()
    execution = nouvelle_execution(demandees, limite, live, surcharges)
    gateway = passerelle(surcharges)

    suites: dict[str, Any] = {}
    jugements: list[Jugement] = []

    with prompts_epingles(epinglages):
        versions = versions_utilisees(AGENTS)
        if "hr" in demandees:
            typer.echo("Suite HR : présélection sur les trois offres…")
            suites["hr"] = await suite_hr.executer(gateway, limite, concurrence)
        if "sales" in demandees:
            typer.echo("Suite Sales : questions commerciales sur FakeCRM…")
            resultat = await suite_sales.executer(gateway, limite, live)
            jugements += resultat.pop("_jugements", [])
            suites["sales"] = resultat
        if "coach" in demandees:
            typer.echo("Suite Coach : comptes rendus annotés…")
            suites["coach"] = await suite_coach.executer(gateway, limite)
        if "adverse" in demandees:
            typer.echo("Suite adverse : injections, fichiers illisibles…")
            suites["adverse"] = await suite_adverse.executer(gateway, limite)

    await gateway.flush_logs()

    violations, respectes = verifier(suites, lire_seuils(fichier_seuils))
    chemin = chemin_rapport(execution, destination)
    feuille = chemin.with_name(chemin.stem + "_relecture.md")
    a_relire = ecrire_feuille(feuille, jugements) if jugements else 0

    rapport = {
        "harnais": {
            "version": VERSION_RAPPORT,
            "date": execution.date,
            "sha": execution.sha,
            "suites": demandees,
            "limite": limite,
            "concurrence": concurrence,
            "live": live,
            "prompt_versions": versions,
            "prompt_versions_epinglees": epinglages,
            "alias_override": surcharges,
        },
        "suites": suites,
        "juge": {
            "verdicts": len(jugements),
            "echantillon_a_relire": a_relire,
            "feuille": feuille.name,
            # Passe à true quand la feuille de relecture a été remplie et que
            # le taux d'accord y a été reporté. Tant que c'est false, les
            # chiffres qui dépendent du juge ne sont pas validés.
            "juge_relu": False,
        },
        "seuils": {
            "fichier": str(fichier_seuils),
            "respectes": len(respectes),
            "violations": violations,
            "detail_respectes": respectes,
        },
    }
    chemin.write_text(
        json.dumps(rapport, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    ecrire_resume(chemin.with_suffix(".md"), rapport)

    typer.echo(f"\nRapport : {chemin}")
    typer.echo(f"Résumé  : {chemin.with_suffix('.md')}")
    if jugements:
        typer.echo(f"Relecture du juge : {feuille} ({a_relire} cas)")
    if violations:
        typer.echo(f"\n{len(violations)} seuil(s) non tenu(s) :")
        for violation in violations:
            typer.echo(f"  - {violation['chemin']} : {violation['motif']}")
        return 1
    typer.echo(f"\nTous les seuils sont tenus ({len(respectes)} vérifiés).")
    return 0


@app.command("verifier")
def verifier_rapport(
    rapport: Annotated[Path, typer.Argument(help="Rapport JSON produit par une exécution")],
    thresholds: Annotated[Path | None, typer.Option(help="Fichier de seuils")] = None,
) -> None:
    """Re-vérifie un rapport archivé contre un fichier de seuils, sans rejouer.

    Sert à deux choses : contrôler qu'un rapport ancien tient toujours les
    seuils d'aujourd'hui, et vérifier le harnais lui-même en resserrant une
    barre pour voir la commande échouer.
    """
    contenu = json.loads(rapport.read_text(encoding="utf-8"))
    violations, respectes = verifier(contenu["suites"], lire_seuils(thresholds or SEUILS))
    for violation in violations:
        typer.echo(f"NON TENU  {violation['chemin']} : {violation['motif']}")
    for respecte in respectes:
        typer.echo(f"tenu      {respecte['chemin']} = {respecte['valeur']}")
    raise typer.Exit(1 if violations else 0)


@app.command("relire")
def relire_juge(
    rapport: Annotated[Path, typer.Argument(help="Rapport JSON dont la feuille a été remplie")],
) -> None:
    """Dépouille la feuille de relecture et inscrit le résultat dans le rapport.

    C'est le geste qui fait passer `juge_relu` à true. Il est séparé de
    l'exécution parce que la relecture est humaine : elle se fait après, et
    elle peut contredire le juge. Le taux d'accord obtenu est écrit dans le
    rapport et rappelé dans le résumé, pour que le chapitre 8 cite un chiffre
    jugé ET relu, jamais un chiffre jugé seul.
    """
    contenu = json.loads(rapport.read_text(encoding="utf-8"))
    feuille = rapport.with_name(contenu["juge"]["feuille"])
    if not feuille.exists():
        typer.echo(f"Feuille introuvable : {feuille}")
        raise typer.Exit(1)

    releve = depouiller_feuille(feuille.read_text(encoding="utf-8"))
    if releve["manquants"]:
        typer.echo(f"{len(releve['manquants'])} cas sans avis : " + ", ".join(releve["manquants"]))
        typer.echo("Remplis la ligne « Ton avis » de chacun avant de relancer.")
        raise typer.Exit(1)

    contenu["juge"] |= {
        "juge_relu": True,
        "relecture": {
            "cas_relus": releve["cas"],
            "accords": releve["accords"],
            "desaccords": releve["desaccords"],
            "taux_accord": releve["taux_accord"],
        },
    }
    rapport.write_text(
        json.dumps(contenu, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    ecrire_resume(rapport.with_suffix(".md"), contenu)
    typer.echo(
        f"Relecture enregistrée : {releve['accords']} accords, "
        f"{releve['desaccords']} désaccords sur {releve['cas']} cas "
        f"(taux d'accord {releve['taux_accord']})."
    )


if __name__ == "__main__":
    app()
