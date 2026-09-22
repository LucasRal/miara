"""GET /dashboard/summary : ce que les agents ont produit pour l'organisation.

Module transverse HORS de core/ (comme `app/usage.py` et `app/queue.py`) : il
agrège les tables des deux domaines métier, ce que core n'a pas le droit de
faire.

Deux partis pris.

**Le gain de temps est une hypothèse, pas une mesure.** Le tableau de bord
affiche des heures économisées à partir d'un temps de tri manuel de référence
(`DASHBOARD_MINUTES_PER_CV`), configurable. L'hypothèse est renvoyée dans la
réponse pour que l'écran puisse la citer : un chiffre de valeur dont on cache
la formule n'est pas défendable dans un mémoire.

**Un seul aller-retour, mis en cache.** L'agrégat coûte plusieurs requêtes de
regroupement ; il est gardé 60 s dans Redis par organisation (carte, section
NE PAS : pas d'agrégation lourde à chaque affichage). Le cache est un confort,
pas une dépendance : s'il est indisponible, on recalcule.
"""

import json
import uuid
from datetime import UTC, datetime
from typing import Annotated, Any

import redis.asyncio as aioredis
import structlog
from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import Context
from app.config import settings
from app.core.crypto import decrypt_credentials
from app.core.models import Integration, LLMCall
from app.hr.models import SCORE_SCORED, Candidate, CandidateScore, ScreeningRun
from app.sales.models import CoachingSession, CrmWrite

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

# Nombre d'événements de l'activité récente sur le tableau de bord.
ACTIVITE = 10
# Borne dure d'une page d'activité : au-delà, l'écran rend plus de lignes
# qu'on n'en lit, et le tri en mémoire cesse d'être gratuit.
ACTIVITE_MAX = 100

# Sources de l'activité : `kind` renvoyé -> table et colonne de date. Sert au
# filtre ET au comptage, pour qu'ajouter une source ne se fasse qu'ici.
SOURCES: dict[str, Any] = {
    "hr_run": ScreeningRun,
    "crm_write": CrmWrite,
    "coaching": CoachingSession,
}


def _cle(org_id: uuid.UUID) -> str:
    return f"dashboard:summary:{org_id}"


async def _depuis_le_cache(org_id: uuid.UUID) -> dict[str, Any] | None:
    try:
        client = aioredis.from_url(settings.REDIS_URL)
        brut = await client.get(_cle(org_id))
        await client.aclose()
    except Exception as exc:  # noqa: BLE001 - un cache absent n'est pas une panne
        logger.warning("dashboard_cache_read_failed", error=str(exc))
        return None
    if brut is None:
        return None
    donnees: dict[str, Any] = json.loads(brut)
    donnees["cached"] = True
    return donnees


async def _vers_le_cache(org_id: uuid.UUID, donnees: dict[str, Any]) -> None:
    try:
        client = aioredis.from_url(settings.REDIS_URL)
        await client.set(_cle(org_id), json.dumps(donnees), ex=settings.DASHBOARD_CACHE_SECONDS)
        await client.aclose()
    except Exception as exc:  # noqa: BLE001
        logger.warning("dashboard_cache_write_failed", error=str(exc))


async def _indicateurs(session: AsyncSession, debut_mois: datetime) -> dict[str, Any]:
    """Les quatre chiffres de l'en-tête, sur le mois en cours."""
    cv_analyses = (
        await session.execute(
            select(func.count())
            .select_from(CandidateScore)
            .where(CandidateScore.status == SCORE_SCORED, CandidateScore.created_at >= debut_mois)
        )
    ).scalar_one()

    ecritures = (
        await session.execute(
            select(func.count())
            .select_from(CrmWrite)
            .where(CrmWrite.status == "created", CrmWrite.created_at >= debut_mois)
        )
    ).scalar_one()

    # Latence des réponses rendues à un humain : la synthèse commerciale et le
    # coach. La notation d'un CV n'attend personne, elle fausserait la moyenne.
    latence = (
        await session.execute(
            select(func.avg(LLMCall.latency_ms)).where(
                LLMCall.created_at >= debut_mois,
                LLMCall.status == "ok",
                LLMCall.agent.in_(("sales.assistant", "sales.coach")),
            )
        )
    ).scalar_one()

    minutes = cv_analyses * settings.DASHBOARD_MINUTES_PER_CV
    return {
        "cv_analyses": cv_analyses,
        "heures_economisees": round(minutes / 60, 1),
        "minutes_par_cv": settings.DASHBOARD_MINUTES_PER_CV,
        "ecritures_crm": ecritures,
        "latence_moyenne_ms": int(latence) if latence is not None else None,
    }


async def _activite(
    session: AsyncSession,
    limite: int = ACTIVITE,
    decalage: int = 0,
    kind: str | None = None,
) -> list[dict[str, Any]]:
    """Événements les plus récents, toutes sources confondues.

    Chaque source est interrogée avec sa propre limite puis l'ensemble est
    trié en mémoire : trois requêtes bornées coûtent moins cher qu'une union
    SQL sur des tables qui n'ont pas la même forme.

    Pour renvoyer la page qui commence au `decalage`-ième événement, il faut
    que chaque source en fournisse `decalage + limite` : le plus ancien de la
    page peut venir de n'importe laquelle. C'est ce qui borne la pagination à
    `ACTIVITE_MAX` — au-delà, l'union SQL serait le bon outil.
    """
    evenements: list[dict[str, Any]] = []
    par_source = decalage + limite

    runs = (
        (
            await session.execute(
                select(ScreeningRun).order_by(ScreeningRun.created_at.desc()).limit(par_source)
            )
        )
        .scalars()
        .all()
    )
    for run in runs:
        stats = run.stats_json or {}
        evenements.append(
            {
                "kind": "hr_run",
                # Les nombres partent bruts : l'accord et la mise en forme
                # sont le travail de l'interface, qui connaît la langue.
                "counts": {
                    "candidates": stats.get("candidates", 0),
                    "scored": stats.get("scored", 0),
                    "failed": stats.get("failed", 0),
                },
                "status": run.status,
                "at": (run.created_at or datetime.now(UTC)).isoformat(),
                "href": f"/hr/{run.job_id}/runs/{run.id}",
            }
        )

    ecritures = (
        (
            await session.execute(
                select(CrmWrite).order_by(CrmWrite.created_at.desc()).limit(par_source)
            )
        )
        .scalars()
        .all()
    )
    for ecriture in ecritures:
        evenements.append(
            {
                "kind": "crm_write",
                # Nom d'outil brut : c'est un identifiant, pas un libellé.
                # L'interface a la table outil -> phrase métier, partagée avec
                # le dialogue de confirmation et la trace de l'agent.
                "tool": ecriture.tool,
                "record_id": ecriture.sf_record_id,
                "error": ecriture.error,
                "status": ecriture.status,
                "at": ecriture.created_at.isoformat(),
                "href": "/sales",
            }
        )

    coachings = (
        (
            await session.execute(
                select(CoachingSession)
                .order_by(CoachingSession.created_at.desc())
                .limit(par_source)
            )
        )
        .scalars()
        .all()
    )
    for session_coach in coachings:
        evenements.append(
            {
                "kind": "coaching",
                "coaching_kind": session_coach.kind,
                "score": session_coach.overall_0_100,
                "status": "done",
                "at": session_coach.created_at.isoformat(),
                "href": "/sales/coach",
            }
        )

    if kind is not None:
        evenements = [e for e in evenements if e["kind"] == kind]
    evenements.sort(key=lambda e: e["at"], reverse=True)
    return evenements[decalage : decalage + limite]


async def _instance_url(session: AsyncSession) -> str | None:
    """URL de l'instance Salesforce de l'org, si elle est connectée.

    Lue depuis l'intégration (donc du contexte de requête, jamais d'un
    argument) ; le jeton chiffré, lui, ne sort jamais d'ici.
    """
    integration = (
        await session.execute(select(Integration).where(Integration.provider == "salesforce"))
    ).scalar_one_or_none()
    if integration is None:
        return None
    try:
        credentials = decrypt_credentials(integration.encrypted_credentials)
    except Exception as exc:  # noqa: BLE001 - une intégration illisible n'est pas une panne
        logger.warning("dashboard_instance_url_failed", error=str(exc))
        return None
    url = credentials.get("instance_url")
    return str(url) if url else None


@router.get("/summary")
async def summary(ctx: Context) -> dict[str, Any]:
    """Agrégat de l'organisation courante, mis en cache 60 s."""
    cache = await _depuis_le_cache(ctx.org_id)
    if cache is not None:
        return cache

    maintenant = datetime.now(UTC)
    debut_mois = maintenant.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    indicateurs = await _indicateurs(ctx.session, debut_mois)
    cv_total = (await ctx.session.execute(select(func.count()).select_from(Candidate))).scalar_one()

    donnees = {
        "organization_id": str(ctx.org_id),
        "period_start": debut_mois.isoformat(),
        "generated_at": maintenant.isoformat(),
        "metrics": indicateurs,
        "cv_total": cv_total,
        "activity": await _activite(ctx.session),
        # Sans elle, un identifiant Salesforce n'est qu'une chaîne de 18
        # caractères ; avec elle, l'interface en fait un lien vers la fiche.
        "crm_instance_url": await _instance_url(ctx.session),
        "cached": False,
    }
    await _vers_le_cache(ctx.org_id, donnees)
    return donnees


@router.get("/activity")
async def activity(
    ctx: Context,
    limit: Annotated[int, Query(ge=1, le=ACTIVITE_MAX)] = 25,
    offset: Annotated[int, Query(ge=0)] = 0,
    kind: Annotated[str | None, Query(description=f"Une source parmi {sorted(SOURCES)}")] = None,
) -> dict[str, Any]:
    """Activité complète de l'organisation, paginée.

    Le tableau de bord n'en montre que les dix derniers événements : c'est un
    aperçu, pas un journal. Cet endpoint est la vue complète vers laquelle il
    renvoie — même forme d'événement, pour que l'écran n'ait qu'un seul
    vocabulaire à connaître.

    Pas de cache ici, contrairement à `/summary` : on pagine, donc chaque page
    est une requête différente, et la fraîcheur compte plus que l'agrégat.
    """
    if kind is not None and kind not in SOURCES:
        raise HTTPException(status_code=422, detail=f"Source inconnue : {kind}")

    tables = [SOURCES[kind]] if kind else list(SOURCES.values())
    total = 0
    for table in tables:
        total += (await ctx.session.execute(select(func.count()).select_from(table))).scalar_one()

    # `offset + limit` ne peut pas dépasser ce que `_activite` sait ramener de
    # chaque source : la page suivante serait incomplète sans le dire.
    if offset + limit > ACTIVITE_MAX:
        raise HTTPException(
            status_code=422,
            detail=f"Au-delà de {ACTIVITE_MAX} événements, affinez avec le filtre par source.",
        )

    return {
        "events": await _activite(ctx.session, limite=limit, decalage=offset, kind=kind),
        "total": total,
        "limit": limit,
        "offset": offset,
        "kinds": sorted(SOURCES),
        "crm_instance_url": await _instance_url(ctx.session),
    }
