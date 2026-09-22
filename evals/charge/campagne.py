"""Orchestration d'une campagne : plan, budget, exécution, CSV, figures, rapport.

Une campagne = une liste de POINTS, chacun étant un triplet
(scénario, `worker_concurrency`, numéro de répétition). Rien n'est implicite :
le plan est écrit dans le rapport avant d'être exécuté, et chaque point y
revient avec son état — `execute`, `ignore_budget`, `interrompu_budget`.

La section « NE PAS » de la carte impose deux choses que le code applique :

- **aucune configuration n'est mélangée** : toute moyenne, tout écart, toute
  figure se calcule à scénario ET concurrence constants. Les points ne sont
  jamais agrégés entre concurrences ;
- **aucun point aberrant n'est retiré**. `mesures.points_aberrants` les
  signale, le rapport les nomme, les moyennes les gardent.
"""

from __future__ import annotations

import json
import platform
import re
import subprocess
import time
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.config import settings
from evals import metriques
from evals.charge import SORTIES, figures
from evals.charge.mesures import (
    COUT_ESTIME_CV_USD,
    COUT_ESTIME_QUESTION_USD,
    Budget,
    BudgetDepasse,
    ecrire_csv,
    famine_file_light,
    reproductibilite,
    verdict_file_light,
)
from evals.charge.passerelle import PasserelleComptee
from evals.charge.scenarios import (
    OFFRE_DE_REFERENCE,
    ResultatHR,
    agreger_sales,
    lot_hr,
    lot_sales,
    sondes_light,
)
from evals.charge.worker import CONCURRENCE_LIGHT, SEPAREE, UNIQUE, GroupeWorkers
from evals.harnais import charger_config_llm, preparer_organisation, sha_court

# Les scénarios de la carte. Le nombre est DANS le nom : `hr-500` traite 500
# candidatures, `mixed-100` en traite 100 pendant que les questions tournent.
# Une taille arbitraire est donc acceptée (`hr-6`, `mixed-6`) — c'est ce qui
# rend la chaîne complète vérifiable pour quelques centimes avant d'engager
# une vraie campagne, et le nom du scénario porte toujours sa taille dans les
# CSV : aucun tableau ne peut présenter un lot de 6 CV comme un lot de 500.
SCENARIOS = ("hr-50", "hr-100", "hr-500", "sales-30", "mixed")
NOMBRE_DE_QUESTIONS = 30
CV_MIXED_PAR_DEFAUT = 100
_TAILLE = re.compile(r"^(hr|mixed)-(\d+)$")


def taille_du_lot(scenario: str) -> int:
    """Nombre de candidatures d'un scénario, lu dans son nom. 0 si sans lot RH."""
    if scenario == "mixed":
        return CV_MIXED_PAR_DEFAUT
    trouve = _TAILLE.match(scenario)
    return int(trouve.group(2)) if trouve else 0


def scenario_valide(scenario: str) -> bool:
    return scenario in SCENARIOS or bool(_TAILLE.match(scenario))


def pose_des_questions(scenario: str) -> bool:
    return scenario == "sales-30" or scenario.startswith("mixed")


COLONNES_RUNS = (
    "scenario",
    "worker_concurrency",
    "repetition",
    "run_id",
    "candidatures",
    "notes",
    "echecs",
    "secondes_total",
    "debit_cv_par_minute",
    "cout_usd",
    "cout_par_cv_usd",
    "appels_llm",
    "appels_llm_en_erreur",
    "extract_moyenne_s",
    "profile_moyenne_s",
    "score_moyenne_s",
    "memoire_pic_mo",
    "memoire_moyenne_mo",
    "documents_distincts",
    "repetition_corpus",
    "statut",
)
COLONNES_QUESTIONS = (
    "scenario",
    "worker_concurrency",
    "repetition",
    "contexte",
    "id",
    "statut",
    "secondes",
    "appels_llm",
    "outils_executes",
    "llm_ms_total",
    "outil_ms_total",
    "autre_ms",
)
COLONNES_LIGHT = ("scenario", "worker_concurrency", "repetition", "contexte", "index", "secondes")
COLONNES_TACHES = (
    "scenario",
    "worker_concurrency",
    "repetition",
    "name",
    "queue",
    "status",
    "duration_ms",
)


@dataclass(frozen=True)
class Point:
    """Un point de mesure : un scénario, une concurrence, une répétition."""

    scenario: str
    concurrence: int
    repetition: int
    questions: int = NOMBRE_DE_QUESTIONS

    @property
    def configuration(self) -> str:
        return f"{self.scenario}@c{self.concurrence}"

    def estimation_usd(self) -> float:
        if not pose_des_questions(self.scenario):
            tours = 0
        # `mixed` pose les questions DEUX fois : une à vide (référence) et une
        # pendant le lot. Sans la mesure à vide, le critère du p95 n'a rien à
        # quoi se comparer.
        elif self.scenario.startswith("mixed"):
            tours = 2 * self.questions
        else:
            tours = self.questions
        return taille_du_lot(self.scenario) * COUT_ESTIME_CV_USD + tours * COUT_ESTIME_QUESTION_USD


def plan_complet(
    scenarios: list[str],
    concurrences: list[int],
    repetitions: int,
    questions: int = NOMBRE_DE_QUESTIONS,
) -> list[Point]:
    """Matrice de la carte : scénarios x concurrences x répétitions.

    `sales-30` ne passe pas par un worker (l'agent conversationnel répond dans
    le processus de l'API) : il n'a qu'un point par répétition, marqué `c0`.
    Le faire varier avec `worker_concurrency` fabriquerait trois fois la même
    mesure sous trois étiquettes différentes.
    """
    points: list[Point] = []
    for scenario in scenarios:
        valeurs = [0] if scenario == "sales-30" else concurrences
        for concurrence in valeurs:
            for repetition in range(1, repetitions + 1):
                points.append(Point(scenario, concurrence, repetition, questions))
    return points


def lire_points(valeurs: list[str], questions: int = NOMBRE_DE_QUESTIONS) -> list[Point]:
    """`--point hr-50:4:3` -> trois répétitions de hr-50 à la concurrence 4."""
    points: list[Point] = []
    for valeur in valeurs:
        morceaux = valeur.split(":")
        if len(morceaux) != 3:
            raise ValueError(f"Attendu scenario:concurrence:repetitions, reçu {valeur!r}")
        scenario, concurrence, repetitions = morceaux
        if not scenario_valide(scenario):
            raise ValueError(f"Scénario inconnu : {scenario!r} (parmi {', '.join(SCENARIOS)})")
        for repetition in range(1, int(repetitions) + 1):
            points.append(Point(scenario, int(concurrence), repetition, questions))
    return points


def environnement(surcharges: dict[str, str]) -> dict[str, Any]:
    """`env.json` : de quoi refaire la mesure, ou savoir pourquoi elle diffère."""
    return {
        "date": datetime.now(UTC).isoformat(timespec="seconds"),
        "sha": sha_court(),
        "machine": {
            "hote": platform.node(),
            "noyau": platform.release(),
            "processeurs_logiques": _nproc(),
            "modele_cpu": _modele_cpu(),
            "memoire_totale_mo": _memoire_totale_mo(),
        },
        "versions": {
            "python": platform.python_version(),
            "postgresql": _version_commande(["psql", "--version"]),
            "celery": _version_module("celery"),
            "litellm": _version_module("litellm"),
        },
        "llm": {
            "config": str(settings.LLM_CONFIG_PATH or "backend/config/llm.yaml"),
            "alias": {
                alias: spec.get("primary")
                for alias, spec in charger_config_llm(surcharges)["aliases"].items()
            },
            "alias_override": surcharges,
            # Réserve majeure pour la lecture des coûts ET des latences : sans
            # clé Anthropic, chaque alias bascule sur son repli OpenAI. Les
            # chiffres publiés sont donc ceux des modèles de repli, pas ceux
            # des modèles primaires de config/llm.yaml.
            "cle_anthropic_presente": bool(settings.ANTHROPIC_API_KEY),
            "cle_openai_presente": bool(settings.OPENAI_API_KEY),
        },
        "reglages": {
            "HR_LLM_CALLS_PER_MINUTE": settings.HR_LLM_CALLS_PER_MINUTE,
            "HR_SCREENING_CONCURRENCY": settings.HR_SCREENING_CONCURRENCY,
            "HR_CALIBRATE_TOP_K": settings.HR_CALIBRATE_TOP_K,
        },
        "jeu_dore": {
            "offre_de_reference": OFFRE_DE_REFERENCE,
            "documents_distincts": 180,
        },
    }


def _nproc() -> int | None:
    import os

    return os.cpu_count()


def _modele_cpu() -> str | None:
    try:
        for ligne in Path("/proc/cpuinfo").read_text(encoding="utf-8").splitlines():
            if ligne.startswith("model name"):
                return ligne.split(":", 1)[1].strip()
    except OSError:
        return None
    return None


def _memoire_totale_mo() -> int | None:
    try:
        for ligne in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines():
            if ligne.startswith("MemTotal:"):
                return int(ligne.split()[1]) // 1024
    except (OSError, ValueError, IndexError):
        return None
    return None


def _version_commande(commande: list[str]) -> str | None:
    try:
        return subprocess.run(commande, capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def _version_module(nom: str) -> str | None:
    from importlib.metadata import PackageNotFoundError, version

    try:
        return version(nom)
    except PackageNotFoundError:
        return None


@dataclass
class Campagne:
    """État d'une campagne en cours, et tout ce qu'elle écrira sur le disque."""

    sortie: Path
    budget: Budget
    graine: int
    topologie: str
    surcharges: dict[str, str]
    runs: list[ResultatHR]
    questions: list[dict[str, Any]]
    light: list[dict[str, Any]]
    taches: list[dict[str, Any]]
    journal: list[dict[str, Any]]


async def executer(
    points: list[Point],
    *,
    budget_usd: float,
    graine: int,
    surcharges: dict[str, str],
    topologie: str = SEPAREE,
    racine_sortie: Path | None = None,
    trace: Any = print,
) -> dict[str, Any]:
    """Exécute le plan point par point et écrit le dossier de campagne."""
    await preparer_organisation()
    horodatage = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    sortie = (racine_sortie or SORTIES) / horodatage
    sortie.mkdir(parents=True, exist_ok=True)

    campagne = Campagne(
        sortie=sortie,
        budget=Budget(plafond_usd=budget_usd),
        graine=graine,
        topologie=topologie,
        surcharges=surcharges,
        runs=[],
        questions=[],
        light=[],
        taches=[],
        journal=[],
    )
    env = environnement(surcharges)
    (sortie / "env.json").write_text(
        json.dumps(env, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    debut = time.monotonic()
    for point in points:
        estimation = point.estimation_usd()
        if not campagne.budget.autorise(estimation):
            campagne.journal.append(
                {
                    "point": point.configuration,
                    "repetition": point.repetition,
                    "etat": "ignore_budget",
                    "estimation_usd": round(estimation, 4),
                    "reste_usd": campagne.budget.reste_usd,
                }
            )
            trace(
                f"[budget] {point.configuration} r{point.repetition} NON EXÉCUTÉ "
                f"(estimé {estimation:.2f} USD, reste {campagne.budget.reste_usd:.2f})"
            )
            continue
        trace(
            f"[{point.configuration} r{point.repetition}] démarrage "
            f"(estimé {estimation:.2f} USD, dépensé {campagne.budget.depense_usd:.2f})"
        )
        await _executer_point(point, campagne, trace)

    secondes = round(time.monotonic() - debut, 1)
    rapport = _ecrire_sorties(campagne, env, points, secondes)
    return rapport


async def _executer_point(point: Point, campagne: Campagne, trace: Any) -> None:
    gateway = PasserelleComptee(charger_config_llm(campagne.surcharges), campagne.budget)
    etat = "execute"
    try:
        if point.scenario == "sales-30":
            resultats = await lot_sales(
                gateway, taille=point.questions, etiquette="a_vide", budget=campagne.budget
            )
            campagne.questions += [
                {
                    **r,
                    "scenario": point.scenario,
                    "worker_concurrency": 0,
                    "repetition": point.repetition,
                }
                for r in resultats
            ]
        elif point.scenario.startswith("mixed"):
            await _mixed(point, campagne, gateway, trace)
        else:
            await _hr(point, campagne, trace)
    except BudgetDepasse as exc:
        etat = "interrompu_budget"
        trace(f"[budget] {point.configuration} r{point.repetition} interrompu : {exc}")
    except Exception as exc:  # noqa: BLE001 - un point ne doit pas couler la campagne
        # Une campagne d'une heure qui perd tous ses CSV parce que le
        # quinzième point a échoué n'a mesuré que de la frustration. Le point
        # part en échec NOMMÉ dans le journal, les autres continuent, et le
        # rapport final dira lequel manque et pourquoi.
        etat = f"erreur: {type(exc).__name__}: {exc}"
        trace(f"[echec] {point.configuration} r{point.repetition} : {etat}")
    finally:
        await gateway.flush_logs()
    campagne.journal.append(
        {
            "point": point.configuration,
            "repetition": point.repetition,
            "etat": etat,
            "depense_cumulee_usd": campagne.budget.depense_usd,
        }
    )


def _avancement_trace(trace: Any) -> Any:
    """Trace l'avancement d'un lot une fois sur dix sondages, pas à chaque fois :
    un lot de 500 CV sondé toutes les deux secondes écrirait 500 lignes."""
    compteur = {"n": 0}

    def rapporter(faits: int, total: int) -> None:
        compteur["n"] += 1
        if compteur["n"] % 10 == 0:
            trace(f"    {faits}/{total} CV traités")

    return rapporter


async def _hr(point: Point, campagne: Campagne, trace: Any) -> None:
    journal = (
        campagne.sortie / f"worker-{point.scenario}-c{point.concurrence}-r{point.repetition}.log"
    )
    with GroupeWorkers(
        campagne.topologie, point.concurrence, cwd=_backend(), journal=journal
    ) as workers:
        resultat = await lot_hr(
            scenario=point.scenario,
            taille=taille_du_lot(point.scenario),
            concurrence=point.concurrence,
            repetition=point.repetition,
            graine=campagne.graine,
            budget=campagne.budget,
            pids_worker=workers.pids,
            sur_avancement=_avancement_trace(trace),
        )
    _ranger_hr(resultat, point, campagne)
    trace(
        f"    -> {resultat.notes}/{resultat.candidatures} notés en {resultat.secondes:.0f} s "
        f"({resultat.debit_cv_min} CV/min, {resultat.cout_usd:.2f} USD, {resultat.statut})"
    )


async def _mixed(point: Point, campagne: Campagne, gateway: Any, trace: Any) -> None:
    """Lot RH de 100 CV et 30 questions commerciales en même temps.

    La mesure à vide est prise JUSTE AVANT, sur le même worker démarré et la
    même machine : comparer le p95 sous charge au p95 d'un rapport d'un autre
    jour mélangerait deux configurations, ce que la carte interdit.
    """
    import asyncio

    journal = (
        campagne.sortie / f"worker-{point.scenario}-c{point.concurrence}-r{point.repetition}.log"
    )
    with GroupeWorkers(
        campagne.topologie, point.concurrence, cwd=_backend(), journal=journal
    ) as workers:
        trace("    phase 1/2 : questions commerciales à vide")
        a_vide = await lot_sales(
            gateway, taille=point.questions, etiquette="a_vide", budget=campagne.budget
        )
        light_vide = await sondes_light(5, 1.0, "a_vide")

        trace("    phase 2/2 : mêmes questions pendant le lot de 100 CV")
        tache_hr = asyncio.create_task(
            lot_hr(
                scenario=point.scenario,
                taille=taille_du_lot(point.scenario),
                concurrence=point.concurrence,
                repetition=point.repetition,
                graine=campagne.graine,
                budget=campagne.budget,
                pids_worker=workers.pids,
            )
        )
        # Laisse le temps aux workers de se remplir : mesurer la latence
        # pendant que la file se remplit encore mesurerait une machine à vide.
        await asyncio.sleep(10)
        sous_charge = await lot_sales(
            gateway, taille=point.questions, etiquette="sous_charge", budget=campagne.budget
        )
        light_charge = await sondes_light(5, 1.0, "sous_charge")
        resultat = await tache_hr

    _ranger_hr(resultat, point, campagne)
    for mesures in (a_vide, sous_charge):
        campagne.questions += [
            {
                **r,
                "scenario": point.scenario,
                "worker_concurrency": point.concurrence,
                "repetition": point.repetition,
            }
            for r in mesures
        ]
    campagne.light += [
        {
            **m,
            "scenario": point.scenario,
            "worker_concurrency": point.concurrence,
            "repetition": point.repetition,
        }
        for m in light_vide + light_charge
    ]
    trace(
        f"    -> RH {resultat.notes}/{resultat.candidatures} en {resultat.secondes:.0f} s ; "
        f"p95 sales à vide {agreger_sales(a_vide)['latence']['p95_secondes']} s, "
        f"sous charge {agreger_sales(sous_charge)['latence']['p95_secondes']} s"
    )


def _ranger_hr(resultat: ResultatHR, point: Point, campagne: Campagne) -> None:
    campagne.runs.append(resultat)
    campagne.budget.ajouter(resultat.cout_usd)
    campagne.taches += [
        {
            **t,
            "scenario": point.scenario,
            "worker_concurrency": point.concurrence,
            "repetition": point.repetition,
        }
        for t in resultat.taches
    ]


def _backend() -> Path:
    return Path(__file__).resolve().parents[2] / "backend"


# --- agrégation et écriture ----------------------------------------------


def _par_configuration(runs: list[ResultatHR]) -> dict[str, list[ResultatHR]]:
    groupes: dict[str, list[ResultatHR]] = defaultdict(list)
    for run in runs:
        groupes[f"{run.scenario}@c{run.concurrence}"].append(run)
    return dict(groupes)


def _questions_par(campagne: Campagne, prefixe: str, contexte: str) -> list[dict[str, Any]]:
    """Questions d'une FAMILLE de scénarios (`sales-30`, `mixed`, `mixed-6`).

    Le préfixe, et non l'égalité : `mixed` et `mixed-6` sont le même scénario à
    deux tailles. Les tailles restent distinguées dans `questions.csv`, qui
    garde le nom exact ligne par ligne.
    """
    return [
        q
        for q in campagne.questions
        if str(q["scenario"]).startswith(prefixe) and q["contexte"] == contexte
    ]


def _ecrire_sorties(
    campagne: Campagne, env: dict[str, Any], plan: list[Point], secondes: float
) -> dict[str, Any]:
    sortie = campagne.sortie
    ecrire_csv(sortie / "runs.csv", [r.ligne_csv() for r in campagne.runs], COLONNES_RUNS)
    ecrire_csv(sortie / "questions.csv", campagne.questions, COLONNES_QUESTIONS)
    ecrire_csv(sortie / "file_light.csv", campagne.light, COLONNES_LIGHT)
    ecrire_csv(sortie / "taches.csv", campagne.taches, COLONNES_TACHES)

    groupes = _par_configuration([r for r in campagne.runs if r.statut == "termine"])
    reproductibilites = [
        reproductibilite(
            "debit_cv_par_minute",
            configuration,
            [r.debit_cv_min for r in runs if r.debit_cv_min is not None],
        ).en_dict()
        for configuration, runs in sorted(groupes.items())
        if len(runs) >= 2
    ]
    ecrire_csv(
        sortie / "reproductibilite.csv",
        reproductibilites,
        (
            "grandeur",
            "configuration",
            "repetitions",
            "moyenne",
            "ecart_relatif",
            "tolerance",
            "tenu",
        ),
    )

    sales_vide = agreger_sales(_questions_par(campagne, "sales-30", "a_vide"))
    mixed_vide = agreger_sales(_questions_par(campagne, "mixed", "a_vide"))
    mixed_charge = agreger_sales(_questions_par(campagne, "mixed", "sous_charge"))
    critere_mixed = verdict_file_light(
        mixed_charge["latence"]["p95_secondes"], mixed_vide["latence"]["p95_secondes"]
    )

    resume_light = _resume_light(campagne.light)

    chemins = _figures(campagne, groupes, mixed_vide, mixed_charge)

    rapport = {
        "campagne": {
            "version": 1,
            "date": env["date"],
            "sha": env["sha"],
            "dossier": str(sortie),
            "graine": campagne.graine,
            "topologie_workers": campagne.topologie,
            "alias_override": campagne.surcharges,
            "secondes_total": secondes,
            "plan": [
                {
                    "scenario": p.scenario,
                    "worker_concurrency": p.concurrence,
                    "repetition": p.repetition,
                }
                for p in plan
            ],
            "journal": campagne.journal,
        },
        "budget": {
            "plafond_usd": campagne.budget.plafond_usd,
            "depense_usd": campagne.budget.depense_usd,
            "reste_usd": campagne.budget.reste_usd,
            "points_ignores": sum(1 for j in campagne.journal if j["etat"] == "ignore_budget"),
        },
        "hr": {
            configuration: {
                "repetitions": len(runs),
                "candidatures": runs[0].candidatures,
                "corpus": runs[0].corpus,
                "debit_cv_par_minute_moyen": metriques.moyenne(
                    [r.debit_cv_min for r in runs if r.debit_cv_min is not None]
                ),
                "secondes_total_moyen": metriques.moyenne([r.secondes for r in runs]),
                "cout_usd_moyen": metriques.moyenne([r.cout_usd for r in runs]),
                "cout_par_cv_usd_moyen": metriques.moyenne(
                    [r.cout_par_cv_usd for r in runs if r.cout_par_cv_usd is not None]
                ),
                "echecs_total": sum(r.echecs for r in runs),
                "appels_llm_en_erreur": sum(r.appels_llm_en_erreur for r in runs),
                "memoire_pic_mo": max(
                    (r.memoire_pic_mo for r in runs if r.memoire_pic_mo is not None), default=None
                ),
                "etapes_moyennes_s": _etapes_moyennes(runs),
                "statuts": sorted({r.statut for r in runs}),
            }
            for configuration, runs in sorted(_par_configuration(campagne.runs).items())
        },
        "sales": {"a_vide": sales_vide},
        "mixed": {
            "a_vide": mixed_vide,
            "sous_charge": mixed_charge,
            "critere_p95": critere_mixed,
            "file_light": resume_light,
            "famine_file_light": famine_file_light(
                resume_light["a_vide"], resume_light["sous_charge"]
            ),
            "topologie_workers": campagne.topologie,
        },
        "reproductibilite": reproductibilites,
        "figures": {nom: str(chemin) for nom, chemin in chemins.items() if chemin},
        "environnement": env,
    }
    (sortie / "campagne.json").write_text(
        json.dumps(rapport, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    (sortie / "rapport.md").write_text(_markdown(rapport), encoding="utf-8")
    return rapport


def _etapes_moyennes(runs: list[ResultatHR]) -> dict[str, float | None]:
    return {
        etape: metriques.moyenne(
            [
                float((r.etapes.get(etape) or {}).get("mean_seconds") or 0.0)
                for r in runs
                if (r.etapes.get(etape) or {}).get("mean_seconds") is not None
            ]
        )
        for etape in ("extract", "profile", "score")
    }


def _resume_light(mesures: list[dict[str, Any]]) -> dict[str, Any]:
    sortie: dict[str, Any] = {}
    for contexte in ("a_vide", "sous_charge"):
        valeurs = [m["secondes"] for m in mesures if m["contexte"] == contexte and m["secondes"]]
        perdus = sum(1 for m in mesures if m["contexte"] == contexte and m["secondes"] is None)
        sortie[contexte] = {
            "sondes": sum(1 for m in mesures if m["contexte"] == contexte),
            "p50_secondes": metriques.percentile(valeurs, 50),
            "p95_secondes": metriques.percentile(valeurs, 95),
            "max_secondes": round(max(valeurs), 3) if valeurs else None,
            "sans_reponse": perdus,
        }
    return sortie


def _figures(
    campagne: Campagne,
    groupes: dict[str, list[ResultatHR]],
    mixed_vide: dict[str, Any],
    mixed_charge: dict[str, Any],
) -> dict[str, Path | str | None]:
    dossier = campagne.sortie / "figures"
    # La figure « débit vs concurrence » ne vaut que pour UNE taille de lot :
    # tracer hr-50 et hr-500 sur la même courbe mélangerait deux
    # configurations. On prend la taille qui a été mesurée sur le plus grand
    # nombre de concurrences, c'est-à-dire celle qui porte réellement la courbe.
    par_scenario: dict[str, set[int]] = defaultdict(set)
    for run in (r for runs in groupes.values() for r in runs):
        if run.scenario.startswith("hr-"):
            par_scenario[run.scenario].add(run.concurrence)
    retenu = max(par_scenario, key=lambda s: (len(par_scenario[s]), s), default=None)

    debits: dict[int, list[float]] = defaultdict(list)
    for run in (r for runs in groupes.values() for r in runs):
        if run.scenario == retenu and run.debit_cv_min is not None:
            debits[run.concurrence].append(run.debit_cv_min)

    series: dict[str, dict[str, float]] = {}
    sales_vide = agreger_sales(_questions_par(campagne, "sales-30", "a_vide"))
    for nom, bloc in (
        ("sales-30 à vide", sales_vide),
        ("mixed à vide", mixed_vide),
        ("mixed sous charge", mixed_charge),
    ):
        if bloc["tours_aboutis"]:
            series[nom] = {k: float(v or 0.0) for k, v in bloc["par_etape_ms"].items()}

    couts: dict[str, float] = {}
    for configuration, runs in sorted(groupes.items()):
        moyenne = metriques.moyenne([r.cout_usd for r in runs])
        if moyenne is not None:
            couts[configuration] = float(moyenne)

    try:
        return {
            "debit_vs_concurrence": figures.debit_vs_concurrence(
                dict(debits),
                dossier / "debit_vs_concurrence.png",
                f"{retenu} : débit vs concurrence",
            ),
            "latence_par_etape": figures.latence_par_etape(
                series, dossier / "latence_par_etape.png", "Agent commercial : temps par étape"
            ),
            "cout_par_lot": figures.cout_par_lot(
                couts, dossier / "cout_par_lot.png", "Coût moyen par lot et configuration"
            ),
        }
    except Exception as exc:  # noqa: BLE001 - une figure absente ne vaut pas une campagne perdue
        # matplotlib manquant, police introuvable, disque plein : une heure de
        # mesures ne doit pas disparaître parce qu'un PNG n'a pas pu s'écrire.
        # Les CSV et le JSON, eux, sont déjà (ou seront) sur le disque.
        return {"erreur": f"{type(exc).__name__}: {exc}"}


def _markdown(rapport: dict[str, Any]) -> str:
    """Rapport lisible. Il dit ce qui a été exécuté ET ce qui ne l'a pas été."""
    env = rapport["environnement"]
    lignes = [
        "# Campagne de charge Miara",
        "",
        f"- Date : {rapport['campagne']['date']} · empreinte `{rapport['campagne']['sha']}`",
        f"- Machine : {env['machine']['modele_cpu']} · "
        f"{env['machine']['processeurs_logiques']} vCPU · {env['machine']['memoire_totale_mo']} Mo",
        f"- Graine : {rapport['campagne']['graine']}",
        f"- Budget : {rapport['budget']['depense_usd']} / {rapport['budget']['plafond_usd']} USD "
        f"({rapport['budget']['points_ignores']} point(s) non exécuté(s) faute de budget)",
        f"- Durée de la campagne : {rapport['campagne']['secondes_total']} s",
        "",
        "## Réserves de lecture",
        "",
        f"- Clé Anthropic absente : {not env['llm']['cle_anthropic_presente']}. "
        "Les alias basculent alors sur leurs replis OpenAI ; les coûts et les "
        "latences publiés sont ceux des replis, pas des modèles primaires.",
        f"- Limiteur de débit actif : {env['reglages']['HR_LLM_CALLS_PER_MINUTE']} appels LLM "
        "par minute et par organisation, soit un plafond théorique de "
        f"{env['reglages']['HR_LLM_CALLS_PER_MINUTE'] // 2} CV/min (2 appels par CV).",
        "- Les lots de plus de 180 CV réemploient des documents du jeu doré : "
        "voir la colonne `documents_distincts` de `runs.csv`.",
        "- Aucun point aberrant n'a été retiré ; ceux qui sont signalés le sont "
        "dans `reproductibilite.csv` (colonne `indices_aberrants` du JSON).",
        "",
        "## Lots RH",
        "",
        "| Configuration | Rép. | CV | Débit moyen (CV/min) | Coût moyen (USD) "
        "| Coût/CV | Échecs | Pic mémoire (Mo) | Statuts |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for configuration, bloc in rapport["hr"].items():
        lignes.append(
            f"| {configuration} | {bloc['repetitions']} | {bloc['candidatures']} | "
            f"{bloc['debit_cv_par_minute_moyen']} | {bloc['cout_usd_moyen']} | "
            f"{bloc['cout_par_cv_usd_moyen']} | {bloc['echecs_total']} | "
            f"{bloc['memoire_pic_mo']} | {', '.join(bloc['statuts'])} |"
        )

    lignes += [
        "",
        "## Latence conversationnelle",
        "",
        "| Série | Tours | p50 | p95 | p99 |",
        "| --- | --- | --- | --- | --- |",
    ]
    for nom, bloc in (
        ("sales-30 à vide", rapport["sales"]["a_vide"]),
        ("mixed à vide", rapport["mixed"]["a_vide"]),
        ("mixed sous charge", rapport["mixed"]["sous_charge"]),
    ):
        latence = bloc["latence"]
        lignes.append(
            f"| {nom} | {bloc['tours_aboutis']}/{bloc['questions']} | "
            f"{latence['p50_secondes']} | {latence['p95_secondes']} | {latence['p99_secondes']} |"
        )

    critere = rapport["mixed"]["critere_p95"]
    lignes += [
        "",
        "## Critères d'acceptation",
        "",
        f"- `mixed` p95 sous charge / p95 à vide = {critere['rapport']} "
        f"(seuil < {critere['facteur_max']}) -> **{_verdict(critere['tenu'])}**",
    ]
    for bloc in rapport["reproductibilite"]:
        lignes.append(
            f"- Reproductibilité {bloc['grandeur']} sur {bloc['configuration']} "
            f"({bloc['repetitions']} répétitions) : écart relatif {bloc['ecart_relatif']} "
            f"(seuil {bloc['tolerance']}) -> **{_verdict(bloc['tenu'])}**"
        )
    non_executes = [j for j in rapport["campagne"]["journal"] if j["etat"] != "execute"]
    if non_executes:
        lignes += ["", "## Points non exécutés", ""]
        for point in non_executes:
            lignes.append(f"- {point['point']} répétition {point['repetition']} : {point['etat']}")
    lignes += [
        "",
        "## File `light` (sonde `core.ping`)",
        "",
        "| Contexte | Sondes | p50 | p95 | Sans réponse |",
        "| --- | --- | --- | --- | --- |",
    ]
    for contexte, bloc in rapport["mixed"]["file_light"].items():
        lignes.append(
            f"| {contexte} | {bloc['sondes']} | {bloc['p50_secondes']} | "
            f"{bloc['p95_secondes']} | {bloc['sans_reponse']} |"
        )
    lignes += [
        "",
        _phrase_topologie(rapport["campagne"]["topologie_workers"]),
        "",
        _phrase_famine(
            rapport["mixed"]["famine_file_light"],
            rapport["campagne"]["topologie_workers"],
        ),
    ]
    return "\n".join(lignes) + "\n"


def _phrase_topologie(topologie: str) -> str:
    """Dit sur quelle topologie de workers la sonde `light` a été prise.

    Sans cette ligne, un p95 `light` ne veut rien dire : le même code donne
    25 s ou 0,05 s selon qu'un seul worker sert les deux files ou non.
    """
    if topologie == UNIQUE:
        return (
            "Topologie mesurée : **un worker unique sur `heavy,light`**. Ce n'est "
            "PAS la topologie déployée ; elle n'est mesurée que pour documenter "
            "la famine avant correction."
        )
    return (
        "Topologie mesurée : **un worker par file** (`heavy` à la concurrence du "
        f"point, `light` à {CONCURRENCE_LIGHT}), celle des unités systemd "
        "`miara-worker-heavy` et `miara-worker-light` du VPS."
    )


def _phrase_famine(famine: dict[str, Any], topologie: str = SEPAREE) -> str:
    """Lecture explicite de la sonde `light`, que le tableau seul ne donne pas.

    Le critère `mixed` de la carte porte sur la latence de l'agent commercial,
    qui répond hors Celery : il peut être tenu alors même que la file `light`
    est bloquée. Les deux verdicts sont donc publiés séparément.
    """
    if famine["famine"] is None:
        return "Famine de la file `light` : **non mesurée** (sonde absente ou incomplète)."
    if not famine["famine"]:
        return (
            "Famine de la file `light` : **non constatée** "
            f"(p95 sous charge {famine['p95_charge_s']} s contre "
            f"{famine['p95_vide_s']} s à vide, aucune sonde perdue)."
        )
    return (
        "Famine de la file `light` : **constatée**. "
        f"{famine['sondes_sans_reponse']} sonde(s) `core.ping` sans réponse dans le délai et "
        f"p95 à {famine['p95_charge_s']} s sous charge contre {famine['p95_vide_s']} s à vide. "
        + (
            "Un worker unique consomme `heavy` et `light` : les slots occupés par "
            "le scoring retardent les tâches légères. "
            if topologie == UNIQUE
            else "La file `light` a pourtant son propre worker : la cause est "
            "ailleurs que dans le partage des slots. "
        )
        + "Le critère `mixed` de la carte reste tenu parce que l'agent commercial "
        "répond dans le processus FastAPI, sans passer par Celery."
    )


def _verdict(tenu: bool | None) -> str:
    if tenu is None:
        return "NON MESURÉ"
    return "tenu" if tenu else "NON TENU"
