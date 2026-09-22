"""Tâches Celery de la présélection (ADR-006 : file `heavy`, sauf classement).

Une chaîne par CV, toutes lancées en parallèle, refermées par un `chord` sur
le classement final :

    chord( [ extract -> profile -> score ] x N )  ->  rank_run   [file light]

Trois règles portent ce fichier.

**Un échec n'arrête pas le lot.** Les tâches attrapent leurs erreurs, marquent
la candidature en échec avec son motif et rendent la main normalement : le
`chord` se referme, les autres CV sont classés. Seules les pannes vraiment
transitoires (réseau, quota fournisseur) donnent lieu à un retry.

**Idempotence par (run, candidat).** Les signatures sont immuables (`.si`) et
chaque étape relit son état en base : un message livré deux fois, un retry
après une coupure, un worker relancé ne produisent jamais de doublon.

**Les arguments voyagent en texte.** Celery sérialise en JSON : les
identifiants traversent en chaînes et sont reconvertis ici. `org_id` vient de
la campagne, jamais d'un contenu produit par un modèle.
"""

import uuid
from typing import Any

import structlog
from celery import chord
from celery.exceptions import Retry
from celery.signals import worker_process_init

from app.config import settings
from app.core.celery_app import celery_app
from app.core.db import engine
from app.core.llm import LLMError
from app.core.worker_loop import run as _run
from app.hr import pipeline
from app.hr.ratelimit import acquire_slot
from app.hr.storage import get_file_store

logger = structlog.get_logger(__name__)

HEAVY = "heavy"
LIGHT = "light"

# Pannes qui valent la peine d'être rejouées : le fournisseur, le réseau, la
# base. Une erreur de validation ou un fichier corrompu ne s'améliorera pas.
TRANSIENT = (LLMError, TimeoutError, ConnectionError, OSError)


def _uuid(value: str | uuid.UUID) -> uuid.UUID:
    return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))


@worker_process_init.connect  # type: ignore[untyped-decorator]
def _reset_connection_pool(**_: Any) -> None:
    """Chaque processus forké repart avec son propre pool de connexions.

    Le fork duplique les sockets PostgreSQL ouverts par le parent : deux
    processus qui écrivent sur la même connexion corrompent le protocole.
    `dispose(close=False)` abandonne les connexions héritées sans les fermer
    (elles appartiennent au parent) et repart sur un pool vide.
    """
    engine.sync_engine.dispose(close=False)


@celery_app.task(  # type: ignore[untyped-decorator]
    name="hr.extract_text", bind=True, max_retries=3, acks_late=True
)
def extract_text(self: Any, run_id: str, candidate_id: str, org_id: str) -> dict[str, Any]:
    """Étape 1 — texte du CV, sans LLM."""
    org, run, candidate = _uuid(org_id), _uuid(run_id), _uuid(candidate_id)
    try:
        text = _run(pipeline.run_extraction(org, run, candidate, get_file_store()))
    except TRANSIENT as exc:
        raise self.retry(exc=exc, countdown=2 ** (self.request.retries + 1)) from exc
    except Exception as exc:  # noqa: BLE001 - le lot doit survivre à tout
        _run(pipeline.mark_failed(org, run, candidate, f"{type(exc).__name__}: {exc}", "extract"))
        return {"candidate_id": candidate_id, "status": "failed"}
    if text is None:
        # `needs_ocr` ou fichier illisible : motif déjà posé sur la candidature.
        _run(pipeline.mark_failed(org, run, candidate, "Texte du CV indisponible", "extract"))
        return {"candidate_id": candidate_id, "status": "failed"}
    return {"candidate_id": candidate_id, "status": "extracted"}


async def _profil_puis_notation(
    org: uuid.UUID, run: uuid.UUID, candidate: uuid.UUID
) -> dict[str, Any] | None:
    """Enchaîne les deux appels au modèle sans ressortir de la boucle."""
    if await pipeline.already_scored(org, run, candidate):
        return None
    text = await pipeline.load_text(org, candidate)
    if text is None:
        return {"status": "skipped"}
    grid = await pipeline.load_grid(org, run)
    acquire_slot(org)
    profile = await pipeline.run_profile(org, run, candidate, text)
    acquire_slot(org)
    return await pipeline.run_scoring(org, run, candidate, text, grid, profile)


@celery_app.task(  # type: ignore[untyped-decorator]
    name="hr.score_candidate", bind=True, max_retries=3, acks_late=True
)
def score_candidate(self: Any, run_id: str, candidate_id: str, org_id: str) -> dict[str, Any]:
    """Étapes 2 et 3 — profil structuré puis notation contre la grille.

    Les deux appels au modèle sont dans la MÊME tâche : ils partagent le texte
    du CV, se suivent immédiatement, et les séparer ferait relire la base sans
    rien gagner en parallélisme (chaque CV est déjà une chaîne indépendante).
    """
    org, run, candidate = _uuid(org_id), _uuid(run_id), _uuid(candidate_id)
    try:
        result = _run(_profil_puis_notation(org, run, candidate))
        if result is None:
            return {"candidate_id": candidate_id, "status": "already_scored"}
        if result.get("status") == "skipped":
            return {"candidate_id": candidate_id, "status": "skipped"}
    except Retry:
        raise
    except TRANSIENT as exc:
        try:
            raise self.retry(exc=exc, countdown=2 ** (self.request.retries + 1)) from exc
        except self.MaxRetriesExceededError:
            _run(pipeline.mark_failed(org, run, candidate, f"{type(exc).__name__}: {exc}", "score"))
            return {"candidate_id": candidate_id, "status": "failed"}
    except Exception as exc:  # noqa: BLE001 - le lot doit survivre à tout
        _run(pipeline.mark_failed(org, run, candidate, f"{type(exc).__name__}: {exc}", "score"))
        return {"candidate_id": candidate_id, "status": "failed"}
    return {"candidate_id": candidate_id, "status": "scored", **result}


@celery_app.task(name="hr.rank_run", bind=True, max_retries=3)  # type: ignore[untyped-decorator]
def rank_run(self: Any, results: list[dict[str, Any]], run_id: str, org_id: str) -> dict[str, Any]:
    """Clôture — classement, compteurs et durées de la campagne (file `light`).

    Reçoit les retours des chaînes (le `chord` les collecte) mais ne s'y fie
    pas : le classement est calculé depuis la base, seule source de vérité si
    une tâche a été rejouée.
    """
    org, run = _uuid(org_id), _uuid(run_id)
    try:
        summary: dict[str, Any] = _run(pipeline.finalize_run(org, run))
    except TRANSIENT as exc:
        raise self.retry(exc=exc, countdown=2 ** (self.request.retries + 1)) from exc

    # Option ADR-007, désactivée par défaut : un second regard comparatif sur
    # les K premiers. Son échec ne remet pas en cause le classement déjà écrit.
    top_k = settings.HR_CALIBRATE_TOP_K
    if top_k > 0 and summary.get("scored", 0) >= 2:
        try:
            summary["calibration"] = _run(pipeline.run_calibration(org, run, top_k))
        except Exception as exc:  # noqa: BLE001 - une option ne casse pas un run
            logger.warning("hr_calibration_failed", run_id=run_id, error=str(exc))
            summary["calibration"] = {"error": f"{type(exc).__name__}"}

    logger.info("hr_run_finished", run_id=run_id, scored=summary.get("scored"))
    return summary


def dispatch_run(run_id: uuid.UUID, org_id: uuid.UUID, candidate_ids: list[uuid.UUID]) -> str:
    """Lance la campagne et rend la main tout de suite (l'API ne bloque pas).

    Une chaîne par CV sur la file `heavy`, refermée par le classement sur la
    file `light` : le classement est court et ne doit pas attendre derrière
    des extractions.
    """
    chaines = [
        extract_text.si(str(run_id), str(cid), str(org_id)).set(queue=HEAVY)
        | score_candidate.si(str(run_id), str(cid), str(org_id)).set(queue=HEAVY)
        for cid in candidate_ids
    ]
    resultat = chord(chaines)(rank_run.s(str(run_id), str(org_id)).set(queue=LIGHT))
    return str(resultat.id)


def dispatch_candidate(run_id: uuid.UUID, org_id: uuid.UUID, candidate_id: uuid.UUID) -> str:
    """Relance UN seul CV dans une campagne déjà lancée.

    Même forme que `dispatch_run` avec une seule chaîne : le `chord` d'un
    élément referme sur `rank_run`, donc le classement et les compteurs de la
    campagne sont recalculés depuis la base après la reprise. Sans cela, le CV
    repris serait noté mais resterait hors du classement affiché.
    """
    return dispatch_run(run_id, org_id, [candidate_id])
