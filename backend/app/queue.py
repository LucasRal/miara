"""File de traitement : ce que les workers ont exécuté pour l'organisation.

Module transverse volontairement HORS de core/, comme `app/usage.py` : il
dépend du contexte d'authentification, que core ne doit jamais importer.

L'écran répond à une question simple et récurrente en exploitation : « est-ce
que ça tourne, et sinon pourquoi ». La relance est réservée à l'encadrement,
parce qu'elle consomme du budget modèle et peut republier une écriture.
"""

from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select

from app import espaces
from app.auth.deps import Context, RequestContext, require_role
from app.core.celery_app import celery_app
from app.core.models import TaskEvent

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/queue", tags=["queue"])

AdminContext = Annotated[RequestContext, Depends(require_role("owner", "admin"))]

# Files déclarées dans app/core/celery_app.py. Une tâche relancée repart dans
# la file où elle avait été publiée, jamais dans la file par défaut.
FILES = {"heavy", "light"}

STATUTS = {"started", "succeeded", "failed"}

# Motifs d'échec traduits. La clé est cherchée dans le texte de l'exception :
# l'utilisateur lit une phrase et ce qu'il peut faire, le détail technique
# reste disponible mais replié côté interface.
MOTIFS: tuple[tuple[str, str], ...] = (
    (
        "UniqueViolation",
        "Ce traitement avait déjà été enregistré : la tâche a été jouée deux fois.",
    ),
    (
        "IntegrityError",
        "Une donnée liée a disparu ou existe en double (CV supprimé, campagne rejouée).",
    ),
    ("CRMAuthError", "La connexion Salesforce de l'organisation n'est plus valide."),
    ("CRMRateLimited", "Salesforce a limité le débit : la tâche peut être relancée."),
    ("TimeoutError", "Le traitement a dépassé le temps imparti."),
    ("ReadTimeout", "Le fournisseur de modèle n'a pas répondu à temps."),
    ("RateLimit", "Le fournisseur de modèle a limité le débit : réessayez plus tard."),
    ("FileNotFoundError", "Le fichier du CV est introuvable sur le serveur."),
    ("ValidationError", "Le modèle a renvoyé une réponse hors du format attendu."),
)


def _motif(error: str | None) -> str | None:
    """Phrase lisible correspondant à une exception, sans sa trace."""
    if not error:
        return None
    for cle, phrase in MOTIFS:
        if cle in error:
            return phrase
    return "Le traitement a échoué. Le détail technique est disponible ci-dessous."


def _sortie(event: TaskEvent) -> dict[str, Any]:
    return {
        "id": str(event.id),
        "task_id": event.task_id,
        "name": event.name,
        "queue": event.queue,
        "status": event.status,
        "trace_id": str(event.trace_id) if event.trace_id else None,
        "started_at": event.started_at.isoformat() if event.started_at else None,
        "finished_at": event.finished_at.isoformat() if event.finished_at else None,
        "duration_ms": event.duration_ms,
        "error": event.error,
        "reason": _motif(event.error),
        "retried": event.retried,
    }


@router.get("/tasks")
async def list_tasks(
    ctx: Context,
    status: Annotated[str | None, Query(description="started | succeeded | failed")] = None,
    limit: int = 25,
    offset: int = 0,
    since_hours: Annotated[
        int | None, Query(description="Fenêtre d'observation, en heures (défaut : 24)")
    ] = 24,
    espace: Annotated[
        str | None, Query(description=f"Espace de travail parmi {list(espaces.ESPACES)}")
    ] = None,
) -> dict[str, Any]:
    """Tâches de l'organisation courante, la plus récente en tête.

    Bornée côté serveur : la file grandit sans limite, la paginer côté client
    reviendrait à tout télécharger d'abord. Le total accompagne la page pour
    que l'interface puisse afficher « page 2 sur 7 ».
    """
    if status is not None and status not in STATUTS:
        raise HTTPException(status_code=422, detail="Statut inconnu")

    espaces.valider(espace)

    filtres = []
    if status is not None:
        filtres.append(TaskEvent.status == status)
    # Les noms de tâches suivent `module.fonction` : l'espace RH ne montre que
    # `hr.*`. Les tâches techniques (`core.*`) n'ont pas d'espace et
    # n'apparaissent donc que sans filtre.
    prefixes = espaces.prefixes(espace)
    if prefixes is not None:
        filtres.append(or_(*(TaskEvent.name.startswith(p) for p in prefixes)))
    if since_hours is not None and since_hours > 0:
        filtres.append(TaskEvent.started_at >= datetime.now(UTC) - timedelta(hours=since_hours))

    total = (
        await ctx.session.execute(select(func.count()).select_from(TaskEvent).where(*filtres))
    ).scalar_one()
    requete = (
        select(TaskEvent)
        .where(*filtres)
        .order_by(TaskEvent.started_at.desc())
        .offset(max(offset, 0))
        .limit(min(max(limit, 1), 100))
    )
    rows = (await ctx.session.execute(requete)).scalars().all()
    return {"tasks": [_sortie(row) for row in rows], "total": total}


@router.post("/tasks/{task_id}/retry", status_code=202)
async def retry_task(task_id: str, ctx: AdminContext) -> dict[str, Any]:
    """Republie une tâche échouée avec SES arguments d'origine.

    Les arguments viennent de la ligne journalisée, donc de ce que l'API avait
    publié depuis le contexte de requête : une relance ne peut pas injecter
    une autre organisation. On refuse tout ce qui n'est pas en échec, pour ne
    pas rejouer une tâche qui a réussi (une écriture CRM, par exemple).
    """
    event = (
        await ctx.session.execute(select(TaskEvent).where(TaskEvent.task_id == task_id))
    ).scalar_one_or_none()
    if event is None:
        raise HTTPException(status_code=404, detail="Tâche introuvable")
    if event.status != "failed":
        raise HTTPException(status_code=409, detail="Seule une tâche en échec peut être relancée")

    # Ceinture et bretelles : la ligne est déjà filtrée par le RLS, on vérifie
    # quand même que l'organisation portée par les arguments est bien la nôtre.
    from app.core.task_events import extract_org_id

    org_des_args = extract_org_id(event.args_json, None)
    if org_des_args is not None and org_des_args != ctx.org_id:
        raise HTTPException(status_code=403, detail="Tâche d'une autre organisation")

    queue = event.queue if event.queue in FILES else "light"
    resultat = celery_app.send_task(event.name, args=event.args_json or [], queue=queue)
    # La ligne existante garde son échec : elle raconte une exécution qui a eu
    # lieu, et la réécrire en « en cours » effacerait ce qui s'est passé. La
    # nouvelle exécution a son propre identifiant Celery, donc sa propre ligne,
    # ouverte par les signaux du worker. Seul le compteur de relances bouge.
    event.retried += 1
    logger.info("task_retried", name=event.name, queue=queue)
    return {"task_id": str(resultat.id), "name": event.name, "queue": queue, "status": "queued"}
