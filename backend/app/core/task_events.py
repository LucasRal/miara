"""Journal des exécutions de tâches Celery, alimenté par les signaux du worker.

Rendre le pipeline asynchrone observable depuis l'interface suppose une trace
en base : les logs du worker ne sont pas consultables par un recruteur, et ne
sont pas cloisonnés par organisation.

Trois choix portent ce fichier.

**Les signaux plutôt que les tâches.** `task_prerun`, `task_postrun` et
`task_failure` instrumentent TOUTES les tâches, y compris celles écrites plus
tard. Aucune tâche n'a à penser à se journaliser, et aucune ne peut oublier.

**L'organisation vient des arguments de la tâche**, qui ont été publiés par
l'API depuis le contexte de requête (contrainte non négociable n°2). Une tâche
sans org identifiable n'est pas journalisée plutôt que d'être rattachée au
hasard : mieux vaut une ligne absente qu'une ligne dans la mauvaise org.

**Le signal ne doit jamais faire échouer la tâche.** Toute erreur d'écriture
est avalée et loguée : une file de traitement indisponible ne doit pas empêcher
57 CV d'être notés.
"""

import time
import uuid
from datetime import UTC, datetime
from typing import Any

import structlog
from celery.signals import task_failure, task_postrun, task_prerun
from sqlalchemy import select, update

from app.core.models import TaskEvent
from app.core.tenant import tenant_session
from app.core.worker_loop import run as _run

logger = structlog.get_logger(__name__)

# Longueur maximale du motif d'échec conservé : de quoi comprendre, pas de
# quoi recopier une trace d'appels entière dans la base.
MAX_ERROR_CHARS = 500

# Dates de départ, gardées en mémoire du processus : le signal de fin ne
# reçoit pas celle du départ, et relire la ligne pour la calculer ferait une
# requête de plus par tâche.
_departs: dict[str, float] = {}


def extract_org_id(args: Any, kwargs: Any) -> uuid.UUID | None:
    """Organisation portée par la tâche, par convention d'appel du projet.

    Les tâches reçoivent `org_id` en argument nommé, ou en DERNIÈRE position :
    `(run_id, candidate_id, org_id)`. D'où la lecture des positionnels à
    l'envers — les prendre dans l'ordre rattacherait la ligne à l'identifiant
    de campagne, c'est-à-dire à une organisation qui n'existe pas.

    On n'accepte qu'un UUID valide : le reste est ignoré, jamais deviné.
    """
    if isinstance(kwargs, dict) and "org_id" in kwargs:
        try:
            return uuid.UUID(str(kwargs["org_id"]))
        except (ValueError, AttributeError, TypeError):
            return None
    if isinstance(args, list | tuple):
        for valeur in reversed(args):
            try:
                return uuid.UUID(str(valeur))
            except (ValueError, AttributeError, TypeError):
                continue
    return None


def _trace_id(args: Any, kwargs: Any) -> uuid.UUID | None:
    """`run_id` (campagne RH) ou `trace_id` : premier UUID des arguments."""
    if isinstance(kwargs, dict):
        for cle in ("run_id", "trace_id"):
            if cle in kwargs:
                try:
                    return uuid.UUID(str(kwargs[cle]))
                except (ValueError, TypeError):
                    return None
    if isinstance(args, list | tuple) and args:
        try:
            return uuid.UUID(str(args[0]))
        except (ValueError, TypeError):
            return None
    return None


def _serialisable(args: Any) -> list[Any]:
    """Arguments tels qu'ils repartiront en cas de relance (des identifiants)."""
    if not isinstance(args, list | tuple):
        return []
    return [a if isinstance(a, str | int | float | bool | type(None)) else str(a) for a in args]


async def _ouvrir(
    org_id: uuid.UUID,
    task_id: str,
    name: str,
    queue: str | None,
    args: list[Any],
    trace: uuid.UUID | None,
) -> None:
    async with tenant_session(org_id) as session:
        # Une relance Celery réutilise le même identifiant de tâche : on met à
        # jour la ligne existante au lieu d'en empiler une par tentative.
        existant = (
            await session.execute(select(TaskEvent).where(TaskEvent.task_id == task_id))
        ).scalar_one_or_none()
        if existant is not None:
            existant.status = "started"
            existant.started_at = datetime.now(UTC)
            existant.finished_at = None
            existant.error = None
            return
        session.add(
            TaskEvent(
                organization_id=org_id,
                task_id=task_id,
                name=name,
                queue=queue,
                status="started",
                args_json=args,
                trace_id=trace,
            )
        )


async def _fermer(
    org_id: uuid.UUID, task_id: str, status: str, duree_ms: int | None, erreur: str | None
) -> None:
    async with tenant_session(org_id) as session:
        await session.execute(
            update(TaskEvent)
            .where(TaskEvent.task_id == task_id)
            .values(
                status=status,
                finished_at=datetime.now(UTC),
                duration_ms=duree_ms,
                error=erreur,
            )
        )


@task_prerun.connect  # type: ignore[untyped-decorator]
def _debut(
    task_id: str | None = None,
    task: Any = None,
    args: Any = None,
    kwargs: Any = None,
    **_: Any,
) -> None:
    org_id = extract_org_id(args, kwargs)
    if org_id is None or task_id is None:
        return
    _departs[task_id] = time.monotonic()
    try:
        queue = getattr(getattr(task, "request", None), "delivery_info", None) or {}
        _run(
            _ouvrir(
                org_id,
                task_id,
                getattr(task, "name", "inconnue"),
                queue.get("routing_key") if isinstance(queue, dict) else None,
                _serialisable(args),
                _trace_id(args, kwargs),
            )
        )
    except Exception as exc:  # noqa: BLE001 - journaliser ne doit rien casser
        logger.warning("task_event_open_failed", task_id=task_id, error=str(exc))


@task_postrun.connect  # type: ignore[untyped-decorator]
def _fin(
    task_id: str | None = None,
    args: Any = None,
    kwargs: Any = None,
    state: str | None = None,
    **_: Any,
) -> None:
    org_id = extract_org_id(args, kwargs)
    if org_id is None or task_id is None:
        return
    depart = _departs.pop(task_id, None)
    duree = int((time.monotonic() - depart) * 1000) if depart is not None else None
    # `task_failure` a déjà posé le motif : on ne l'écrase pas par un état générique.
    if state == "FAILURE":
        return
    try:
        _run(_fermer(org_id, task_id, "succeeded", duree, None))
    except Exception as exc:  # noqa: BLE001
        logger.warning("task_event_close_failed", task_id=task_id, error=str(exc))


@task_failure.connect  # type: ignore[untyped-decorator]
def _echec(
    task_id: str | None = None,
    exception: BaseException | None = None,
    args: Any = None,
    kwargs: Any = None,
    **_: Any,
) -> None:
    org_id = extract_org_id(args, kwargs)
    if org_id is None or task_id is None:
        return
    depart = _departs.pop(task_id, None)
    duree = int((time.monotonic() - depart) * 1000) if depart is not None else None
    motif = f"{type(exception).__name__}: {exception}"[:MAX_ERROR_CHARS]
    try:
        _run(_fermer(org_id, task_id, "failed", duree, motif))
    except Exception as exc:  # noqa: BLE001
        logger.warning("task_event_fail_failed", task_id=task_id, error=str(exc))
