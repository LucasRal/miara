"""Les cinq scénarios de la campagne : `hr-N`, `sales-N`, `mixed`.

Le RH passe par les tâches Celery de production (`dispatch_run`), le
commercial par le runtime d'agent de production. Aucun prompt, aucune grille,
aucun calcul de note n'est réécrit ici : la campagne mesure le produit.

**Le corpus de 500 CV n'est pas 500 CV distincts.** Le jeu doré contient 180
documents (3 offres x 60). Au-delà, les fichiers sont réemployés par
répétition déterministe de la liste mélangée à graine fixe : le CV numéro 180+k
est le même document que le numéro k, déposé une seconde fois comme une
candidature distincte. C'est acceptable pour mesurer un débit, une mémoire et
un coût — ce sont les mêmes octets, les mêmes appels au modèle, le même
travail — et c'est inacceptable pour en tirer une mesure de qualité. Aucun
chiffre de qualité n'est donc produit par cette campagne : le harnais
(`make eval`) s'en charge, sur le jeu complet et sans répétition.
"""

from __future__ import annotations

import asyncio
import random
import time
import uuid
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sqlalchemy import Text, cast, func, select

from app.core.agents import runtime
from app.core.agents.context import RequestContext
from app.core.celery_app import celery_app
from app.core.llm import LLMGateway
from app.core.models import LLMCall, TaskEvent
from app.core.tenant import tenant_session
from app.hr import ratelimit
from app.hr.criteria import Criteria
from app.hr.models import RUN_DONE, CandidateScore, ScreeningRun
from app.hr.storage import FileStore
from app.hr.tasks import dispatch_run
from app.sales.agents.assistant import sales_assistant
from app.sales.crm.factory import clear_fake
from evals import metriques
from evals.charge.mesures import Budget, BudgetDepasse, debit_cv_par_minute
from evals.charge.worker import ReleveMemoire
from evals.harnais import ORG_EVAL, USER_EVAL, dossier_donnees
from evals.suites.hr import creer_campagne, offres_disponibles
from evals.suites.sales import preparer_crm
from scripts.crm_seed import lire_questions

# Offre dont la grille sert de référence pour TOUS les CV du lot de charge.
# Un CV d'assistante RH noté contre une grille de développeur reste un CV à
# extraire, structurer et noter : le travail mesuré est identique. La note
# produite, elle, n'a aucun sens — raison de plus pour ne publier aucun
# chiffre de qualité depuis cette campagne.
OFFRE_DE_REFERENCE = "developpeur-full-stack"

INTERVALLE_SONDAGE_S = 2.0


def corpus(taille: int, graine: int) -> list[Path]:
    """`taille` fichiers de CV, tirés du jeu doré par répétition déterministe.

    L'ordre est mélangé une fois avec la graine (les 180 CV sont rangés par
    offre puis par strate : les prendre dans l'ordre alphabétique ferait un lot
    homogène au début et un autre à la fin, et le débit dépendrait de l'endroit
    où on coupe). Puis la liste est répétée cycliquement jusqu'à `taille`.
    """
    fichiers = sorted(
        chemin
        for offre in offres_disponibles()
        for chemin in dossier_donnees("hr", offre, "cv").iterdir()
        if chemin.is_file()
    )
    if not fichiers:
        raise RuntimeError("Jeu doré introuvable : lancer `make gen-data`")
    random.Random(graine).shuffle(fichiers)
    return [fichiers[i % len(fichiers)] for i in range(taille)]


def repetition_du_corpus(taille: int, distincts: int) -> dict[str, Any]:
    """De quoi écrire noir sur blanc, dans le rapport, ce que vaut le corpus."""
    return {
        "candidatures": taille,
        "documents_distincts": min(taille, distincts),
        "repetition_moyenne": round(taille / min(taille, distincts), 2),
    }


async def _cout_et_erreurs(run_id: uuid.UUID) -> tuple[float, int, int]:
    """Coût USD, appels, appels en erreur d'une campagne, relus dans `llm_calls`.

    Une seule source de vérité pour le coût, la même que `stats_json` et que la
    page Usage : `trace_id` vaut l'identifiant de campagne.
    """
    async with tenant_session(ORG_EVAL) as session:
        ligne = (
            await session.execute(
                select(
                    func.coalesce(func.sum(LLMCall.cost_usd), 0),
                    func.count(),
                    func.count().filter(LLMCall.status != "ok"),
                ).where(LLMCall.trace_id == run_id)
            )
        ).one()
    return float(ligne[0]), int(ligne[1]), int(ligne[2])


async def _avancement(run_id: uuid.UUID) -> tuple[int, str]:
    async with tenant_session(ORG_EVAL) as session:
        notes = (
            await session.execute(
                select(func.count())
                .select_from(CandidateScore)
                .where(CandidateScore.run_id == run_id)
            )
        ).scalar_one()
        run = await session.get(ScreeningRun, run_id)
        return int(notes), (run.status if run is not None else "inconnu")


async def taches_du_lot(run_id: uuid.UUID) -> list[dict[str, Any]]:
    """Journal `task_events` d'une campagne, les deux files comprises.

    La condition sur `trace_id` ne suffit pas : `hr.rank_run` reçoit en
    premier argument la liste des retours du `chord`, pas l'identifiant de
    campagne, et `app.core.task_events` ne sait donc pas lui rattacher une
    trace. Or `rank_run` est précisément la tâche de la file `light` — la
    laisser de côté priverait le chapitre 8 de la seule tâche légère du
    pipeline. On la retrouve par l'identifiant de campagne présent dans ses
    arguments journalisés.
    """
    motif = f"%{run_id}%"
    async with tenant_session(ORG_EVAL) as session:
        lignes = (
            (
                await session.execute(
                    select(TaskEvent)
                    .where(
                        (TaskEvent.trace_id == run_id) | cast(TaskEvent.args_json, Text).like(motif)
                    )
                    .order_by(TaskEvent.started_at)
                )
            )
            .scalars()
            .all()
        )
    return [
        {
            "name": t.name,
            "queue": t.queue,
            "status": t.status,
            "duration_ms": t.duration_ms,
            "error": t.error,
        }
        for t in lignes
    ]


@dataclass
class ResultatHR:
    """Ce qu'un lot RH laisse derrière lui, tel quel dans le CSV."""

    scenario: str
    concurrence: int
    repetition: int
    run_id: str
    candidatures: int
    notes: int
    echecs: int
    secondes: float
    debit_cv_min: float | None
    cout_usd: float
    appels_llm: int
    appels_llm_en_erreur: int
    statut: str
    memoire_pic_mo: float | None = None
    memoire_moyenne_mo: float | None = None
    etapes: dict[str, Any] = field(default_factory=dict)
    taches: list[dict[str, Any]] = field(default_factory=list)
    corpus: dict[str, Any] = field(default_factory=dict)

    @property
    def cout_par_cv_usd(self) -> float | None:
        return round(self.cout_usd / self.notes, 6) if self.notes else None

    def ligne_csv(self) -> dict[str, Any]:
        etapes = self.etapes or {}
        return {
            "scenario": self.scenario,
            "worker_concurrency": self.concurrence,
            "repetition": self.repetition,
            "run_id": self.run_id,
            "candidatures": self.candidatures,
            "notes": self.notes,
            "echecs": self.echecs,
            "secondes_total": self.secondes,
            "debit_cv_par_minute": self.debit_cv_min,
            "cout_usd": round(self.cout_usd, 6),
            "cout_par_cv_usd": self.cout_par_cv_usd,
            "appels_llm": self.appels_llm,
            "appels_llm_en_erreur": self.appels_llm_en_erreur,
            "extract_moyenne_s": (etapes.get("extract") or {}).get("mean_seconds"),
            "profile_moyenne_s": (etapes.get("profile") or {}).get("mean_seconds"),
            "score_moyenne_s": (etapes.get("score") or {}).get("mean_seconds"),
            "memoire_pic_mo": self.memoire_pic_mo,
            "memoire_moyenne_mo": self.memoire_moyenne_mo,
            "documents_distincts": self.corpus.get("documents_distincts"),
            "repetition_corpus": self.corpus.get("repetition_moyenne"),
            "statut": self.statut,
        }


async def lot_hr(
    *,
    scenario: str,
    taille: int,
    concurrence: int,
    repetition: int,
    graine: int,
    budget: Budget,
    pids_worker: Sequence[int] = (),
    timeout_s: float = 3600.0,
    sur_avancement: Any = None,
) -> ResultatHR:
    """Un lot de `taille` CV, publié sur la file `heavy` et suivi jusqu'au bout.

    Le budget est vérifié À CHAUD pendant le lot : la dépense réelle est relue
    dans `llm_calls` à chaque sondage. Si le plafond est franchi, les messages
    encore en file sont purgés et le lot s'arrête là, en le disant (`statut`).
    Un lot interrompu n'est jamais présenté comme un lot terminé.
    """
    store = FileStore()
    fichiers = corpus(taille, graine)
    racine = dossier_donnees("hr", OFFRE_DE_REFERENCE)
    grille = Criteria.model_validate_json((racine / "grille.json").read_text(encoding="utf-8"))
    texte_offre = (racine / "offre.md").read_text(encoding="utf-8")

    run_id, noms = await creer_campagne(
        f"charge-{scenario}-c{concurrence}-r{repetition}", grille, texte_offre, fichiers, store
    )
    # Le compteur de débit est partagé par toutes les campagnes de
    # l'organisation : sans remise à zéro, la fenêtre laissée pleine par le lot
    # précédent ferait patienter le suivant dès sa première seconde.
    ratelimit.reset(ORG_EVAL)

    memoire = ReleveMemoire()
    debut = time.monotonic()
    dispatch_run(run_id, ORG_EVAL, list(noms))

    statut = "termine"
    notes = 0
    while True:
        await asyncio.sleep(INTERVALLE_SONDAGE_S)
        if pids_worker:
            memoire.ajouter(*pids_worker)
        notes, etat = await _avancement(run_id)
        cout, _, _ = await _cout_et_erreurs(run_id)
        if sur_avancement is not None:
            sur_avancement(notes, taille)
        if etat == RUN_DONE:
            break
        # `cout` est la dépense de CE lot ; `budget.depense_usd` celle des
        # scénarios déjà clos. Le plafond porte sur la campagne entière.
        if budget.depense_usd + cout > budget.plafond_usd:
            celery_app.control.purge()
            statut = "interrompu_budget"
            break
        if time.monotonic() - debut > timeout_s:
            celery_app.control.purge()
            statut = "interrompu_delai"
            break

    secondes = round(time.monotonic() - debut, 2)
    # La campagne passe en `done` DANS `rank_run` : au moment où on le voit, le
    # signal `task_postrun` de cette tâche n'a pas encore écrit sa ligne, et la
    # journalisation d'appel LLM de la dernière notation est peut-être encore
    # en vol. Ce délai sert à relire un état stabilisé, pas à laisser du temps
    # au traitement — la durée du lot, elle, a déjà été arrêtée juste au-dessus.
    await asyncio.sleep(2.0)
    cout, appels, erreurs = await _cout_et_erreurs(run_id)
    async with tenant_session(ORG_EVAL) as session:
        run = await session.get(ScreeningRun, run_id)
        stats = dict(run.stats_json or {}) if run is not None else {}

    notes_finales = int(stats.get("scored", notes))
    return ResultatHR(
        scenario=scenario,
        concurrence=concurrence,
        repetition=repetition,
        run_id=str(run_id),
        candidatures=taille,
        notes=notes_finales,
        echecs=int(stats.get("failed", 0)),
        secondes=secondes,
        debit_cv_min=debit_cv_par_minute(notes_finales, secondes),
        cout_usd=round(cout, 6),
        appels_llm=appels,
        appels_llm_en_erreur=erreurs,
        statut=statut,
        memoire_pic_mo=memoire.pic_mo,
        memoire_moyenne_mo=memoire.moyenne_mo,
        etapes=stats.get("steps", {}),
        taches=await taches_du_lot(run_id),
        corpus=repetition_du_corpus(taille, 180),
    )


# --- commercial -----------------------------------------------------------


async def une_question(
    question: dict[str, Any], gateway: LLMGateway, etiquette: str
) -> dict[str, Any]:
    """Un tour d'agent complet, décomposé en temps LLM et temps outil.

    La décomposition vient des événements du runtime (`llm_call`, `tool_exec`),
    qui portent déjà leur latence : rien n'est chronométré deux fois.
    """
    evenements: list[dict[str, Any]] = []
    ctx = RequestContext(org_id=ORG_EVAL, user_id=USER_EVAL, role="sales")
    debut = time.monotonic()
    statut = "final"
    try:
        resultat = await runtime.run(
            sales_assistant, question["question"], ctx, gateway=gateway, observer=evenements.append
        )
        if not isinstance(resultat, runtime.Final):
            statut = type(resultat).__name__
    except Exception as exc:  # noqa: BLE001 - une question ne doit pas couler la campagne
        statut = f"erreur: {type(exc).__name__}"
    secondes = round(time.monotonic() - debut, 3)

    llm_ms = [e["latency_ms"] for e in evenements if e["kind"] == "llm_call" and e["latency_ms"]]
    outil_ms = [e["latency_ms"] for e in evenements if e["kind"] == "tool_exec" and e["latency_ms"]]
    return {
        "contexte": etiquette,
        "id": question["id"],
        "statut": statut,
        "secondes": secondes,
        "appels_llm": len(llm_ms),
        "outils_executes": len(outil_ms),
        "llm_ms_total": sum(llm_ms),
        "outil_ms_total": sum(outil_ms),
        # Le reste du tour : sérialisation, base, boucle. Ce qui n'est ni
        # modèle ni outil doit se voir, sinon la somme des parts ne fait pas
        # le tout et personne ne sait où sont passées les secondes.
        "autre_ms": max(0, int(secondes * 1000) - sum(llm_ms) - sum(outil_ms)),
    }


async def lot_sales(
    gateway: LLMGateway, *, taille: int | None, etiquette: str, budget: Budget
) -> list[dict[str, Any]]:
    """Les questions du jeu doré, posées l'une après l'autre.

    En série, et non en parallèle : la latence conversationnelle (H3) est celle
    que vit UN utilisateur. Des questions parallèles mesureraient un débit
    d'agent, ce que la carte ne demande pas.
    """
    questions = lire_questions()
    if taille is not None:
        questions = questions[:taille]
    await preparer_crm()
    resultats: list[dict[str, Any]] = []
    try:
        for question in questions:
            if budget.depasse:
                raise BudgetDepasse(f"Plafond atteint après {len(resultats)} questions")
            resultats.append(await une_question(question, gateway, etiquette))
    finally:
        clear_fake(ORG_EVAL)
    return resultats


def agreger_sales(resultats: list[dict[str, Any]]) -> dict[str, Any]:
    """p50/p95/p99, part LLM et part outil. Percentiles du harnais, pas d'autres."""
    aboutis = [r for r in resultats if r["statut"] == "final"]
    latences = [r["secondes"] for r in aboutis]
    return {
        "questions": len(resultats),
        "tours_aboutis": len(aboutis),
        "latence": {
            "p50_secondes": metriques.percentile(latences, 50),
            "p95_secondes": metriques.percentile(latences, 95),
            "p99_secondes": metriques.percentile(latences, 99),
            "max_secondes": round(max(latences), 3) if latences else None,
        },
        "par_etape_ms": {
            "llm_moyen": metriques.moyenne([r["llm_ms_total"] for r in aboutis]),
            "outil_moyen": metriques.moyenne([r["outil_ms_total"] for r in aboutis]),
            "autre_moyen": metriques.moyenne([r["autre_ms"] for r in aboutis]),
        },
        "etapes": {
            "appels_llm_moyen": metriques.moyenne([r["appels_llm"] for r in aboutis]),
            "outils_moyen": metriques.moyenne([r["outils_executes"] for r in aboutis]),
            "non_aboutis": len(resultats) - len(aboutis),
        },
    }


# --- file light -----------------------------------------------------------


def sonde_light(timeout: float = 30.0) -> float | None:
    """Aller-retour d'un `core.ping` publié sur la file `light`, en secondes.

    C'est la mesure de famine : si les workers sont tous occupés par des CV de
    la file `heavy`, une tâche courte de la file `light` attend, et cette
    attente se voit ici. None quand le ping n'est pas revenu dans le délai —
    ce qui est un résultat, pas une absence de résultat.
    """
    debut = time.monotonic()
    resultat = celery_app.send_task("core.ping", queue="light")
    try:
        resultat.get(timeout=timeout)
    except Exception:  # noqa: BLE001 - le délai dépassé EST la mesure
        return None
    finally:
        resultat.forget()
    return round(time.monotonic() - debut, 3)


async def sondes_light(nombre: int, intervalle: float, etiquette: str) -> list[dict[str, Any]]:
    mesures: list[dict[str, Any]] = []
    for index in range(nombre):
        valeur = await asyncio.to_thread(sonde_light)
        mesures.append({"contexte": etiquette, "index": index, "secondes": valeur})
        await asyncio.sleep(intervalle)
    return mesures
