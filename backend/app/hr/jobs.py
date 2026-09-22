"""Endpoints du socle RH : offres, grille de critères, dépôt des CV.

Parcours couvert par cette carte :

1. le RH crée une offre (`POST /hr/jobs`) — statut `draft` ;
2. il demande une grille (`POST /hr/jobs/{id}/criteria/suggest`), qui est
   proposée par le modèle mais n'engage rien ;
3. il l'ajuste et la valide (`PUT /hr/jobs/{id}/criteria`) — statut `ready` ;
4. il dépose les CV (`POST /hr/jobs/{id}/candidates`).

La notation n'est PAS ici (carte suivante) : ce module s'arrête à des
candidatures en statut `uploaded` et à une grille validée. `ensure_ready`
expose la seule règle que le pipeline devra respecter — pas d'analyse sans
grille validée par un humain.
"""

import uuid
from datetime import UTC, datetime
from typing import Annotated, Any

import structlog
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from app.auth.deps import RequestContext as AuthContext
from app.auth.deps import require_role
from app.config import settings
from app.core.llm import LLMGateway, gateway_dependency
from app.hr.criteria import Criteria, suggest_criteria
from app.hr.models import (
    CANDIDATE_UPLOADED,
    JOB_DRAFT,
    JOB_READY,
    Candidate,
    Job,
    ScreeningRun,
)
from app.hr.storage import ALLOWED_KINDS, FileStore, get_file_store, sniff_kind

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/hr", tags=["hr"])

# Le module RH est réservé aux recruteurs et à l'encadrement de l'org.
HRContext = Annotated[AuthContext, Depends(require_role("owner", "admin", "hr"))]
Gateway = Annotated[LLMGateway, Depends(gateway_dependency)]
Store = Annotated[FileStore, Depends(get_file_store)]

MAX_TITLE_CHARS = 200
MAX_DESCRIPTION_CHARS = 20000


class JobIn(BaseModel):
    title: str = Field(min_length=3, max_length=MAX_TITLE_CHARS)
    description_text: str = Field(min_length=20, max_length=MAX_DESCRIPTION_CHARS)


async def _last_runs(ctx: AuthContext, job_ids: list[uuid.UUID]) -> dict[uuid.UUID, dict[str, Any]]:
    """Dernière campagne de chaque offre, en une seule requête.

    La liste des offres l'affiche pour chaque ligne : une requête par offre
    ferait N+1 appels pour une information d'en-tête.
    """
    if not job_ids:
        return {}
    rows = (
        (
            await ctx.session.execute(
                select(ScreeningRun)
                .where(ScreeningRun.job_id.in_(job_ids))
                .order_by(ScreeningRun.created_at.desc())
            )
        )
        .scalars()
        .all()
    )
    dernier: dict[uuid.UUID, dict[str, Any]] = {}
    for run in rows:
        dernier.setdefault(
            run.job_id,
            {
                "run_id": str(run.id),
                "status": run.status,
                "stats": run.stats_json,
                "created_at": run.created_at.isoformat() if run.created_at else None,
            },
        )
    return dernier


def _job_out(
    job: Job, candidates: int = 0, last_run: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Représentation publique d'une offre. `file_path` n'apparaît nulle part."""
    grid = job.criteria_json or {}
    return {
        "id": str(job.id),
        "title": job.title,
        "description_text": job.description_text,
        "status": job.status,
        "criteria": grid.get("criteria", []),
        "criteria_prompt_version": job.criteria_prompt_version,
        "candidates": candidates,
        "last_run": last_run,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "archived_at": job.archived_at.isoformat() if job.archived_at else None,
    }


def _candidate_out(candidate: Candidate) -> dict[str, Any]:
    """Le chemin de stockage reste interne (carte [HR] socle, section NE PAS)."""
    return {
        "id": str(candidate.id),
        "original_filename": candidate.original_filename,
        "mime": candidate.mime,
        "size_bytes": candidate.size_bytes,
        "status": candidate.status,
        "created_at": candidate.created_at.isoformat() if candidate.created_at else None,
    }


def ensure_ready(job: Job) -> None:
    """Garde d'entrée du pipeline de présélection : grille validée obligatoire.

    Appelée par la carte de notation avant toute campagne. Une grille seulement
    suggérée ne suffit pas : c'est la validation humaine qui fait du protocole
    d'évaluation un choix du recruteur, pas du modèle (ADR-007).
    """
    if job.status != JOB_READY:
        raise HTTPException(
            status_code=409,
            detail="La grille de critères doit être validée avant toute analyse",
        )


async def _get_job(ctx: AuthContext, job_id: uuid.UUID) -> Job:
    """Offre de l'organisation courante. Le RLS rend invisibles celles des
    autres organisations : elles sortent en 404, pas en 403."""
    job = await ctx.session.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Offre introuvable")
    return job


@router.post("/jobs", status_code=201)
async def create_job(body: JobIn, ctx: HRContext) -> dict[str, Any]:
    job = Job(
        organization_id=ctx.org_id,
        title=body.title,
        description_text=body.description_text,
        status=JOB_DRAFT,
        created_by=ctx.user_id,
    )
    ctx.session.add(job)
    await ctx.session.flush()
    await ctx.session.refresh(job)
    logger.info("hr_job_created", job_id=str(job.id))
    return _job_out(job)


@router.get("/jobs")
async def list_jobs(
    ctx: HRContext,
    limit: int = 50,
    archived: Annotated[
        bool | None,
        Query(description="false (défaut) : offres actives · true : archivées · null : toutes"),
    ] = False,
) -> list[dict[str, Any]]:
    rows = (
        await ctx.session.execute(select(Candidate.job_id, func.count()).group_by(Candidate.job_id))
    ).all()
    counts: dict[uuid.UUID, int] = {job_id: total for job_id, total in rows}
    requete = select(Job).order_by(Job.created_at.desc()).limit(min(limit, 200))
    if archived is True:
        requete = requete.where(Job.archived_at.is_not(None))
    elif archived is False:
        requete = requete.where(Job.archived_at.is_(None))
    jobs = (await ctx.session.execute(requete)).scalars().all()
    runs = await _last_runs(ctx, [job.id for job in jobs])
    return [_job_out(job, counts.get(job.id, 0), runs.get(job.id)) for job in jobs]


@router.get("/jobs/{job_id}")
async def get_job(job_id: uuid.UUID, ctx: HRContext) -> dict[str, Any]:
    job = await _get_job(ctx, job_id)
    total = (
        await ctx.session.execute(
            select(func.count()).select_from(Candidate).where(Candidate.job_id == job_id)
        )
    ).scalar_one()
    runs = await _last_runs(ctx, [job.id])
    return _job_out(job, total, runs.get(job.id))


class ArchiveIn(BaseModel):
    archived: bool


@router.patch("/jobs/{job_id}/archive")
async def archive_job(job_id: uuid.UUID, data: ArchiveIn, ctx: HRContext) -> dict[str, Any]:
    """Archive ou désarchive une offre.

    Jamais de suppression : les candidatures et les analyses déjà produites
    restent consultables, l'offre sort seulement de la liste courante.
    """
    job = await _get_job(ctx, job_id)
    job.archived_at = datetime.now(UTC) if data.archived else None
    await ctx.session.flush()
    logger.info("job_archived", job_id=str(job_id), archived=data.archived)
    total = (
        await ctx.session.execute(
            select(func.count()).select_from(Candidate).where(Candidate.job_id == job_id)
        )
    ).scalar_one()
    runs = await _last_runs(ctx, [job.id])
    return _job_out(job, total, runs.get(job.id))


@router.post("/jobs/{job_id}/criteria/suggest")
async def suggest(job_id: uuid.UUID, ctx: HRContext, gateway: Gateway) -> dict[str, Any]:
    """Grille proposée à partir du texte de l'offre. N'engage rien : l'offre
    reste en `draft` tant que le RH n'a pas validé."""
    job = await _get_job(ctx, job_id)
    grid, prompt_version = await suggest_criteria(
        gateway, org_id=ctx.org_id, title=job.title, description=job.description_text
    )
    job.criteria_json = grid.model_dump(mode="json")
    job.criteria_prompt_version = prompt_version
    logger.info(
        "hr_criteria_suggested",
        job_id=str(job.id),
        criteria=len(grid.criteria),
        prompt_version=prompt_version,
    )
    return {
        "job_id": str(job.id),
        "status": job.status,
        "prompt_version": prompt_version,
        "criteria": grid.model_dump(mode="json")["criteria"],
    }


@router.put("/jobs/{job_id}/criteria")
async def validate_criteria(job_id: uuid.UUID, body: Criteria, ctx: HRContext) -> dict[str, Any]:
    """Validation (et édition) de la grille par le RH : l'offre passe en `ready`.

    Le corps est revalidé par le même schéma que la suggestion : un RH ne peut
    pas non plus déposer une grille de trois critères ou aux poids hors bornes.
    """
    job = await _get_job(ctx, job_id)
    job.criteria_json = body.model_dump(mode="json")
    job.status = JOB_READY
    logger.info("hr_criteria_validated", job_id=str(job.id), criteria=len(body.criteria))
    return _job_out(job)


@router.post("/jobs/{job_id}/candidates", status_code=201)
async def upload_candidates(
    job_id: uuid.UUID,
    ctx: HRContext,
    store: Store,
    files: Annotated[list[UploadFile], File(description="CV au format PDF ou DOCX")],
) -> dict[str, Any]:
    """Dépôt de CV. Chaque fichier est accepté ou refusé indépendamment :
    un lot de vingt CV n'est pas perdu parce que l'un d'eux est illisible."""
    job = await _get_job(ctx, job_id)
    if len(files) > settings.HR_MAX_UPLOAD_FILES:
        raise HTTPException(
            status_code=422,
            detail=f"{settings.HR_MAX_UPLOAD_FILES} fichiers au maximum par requête",
        )

    max_bytes = settings.HR_MAX_FILE_MB * 1024 * 1024
    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, str]] = []

    for upload in files:
        # Nom d'affichage seulement : jamais utilisé pour construire un chemin.
        display_name = (upload.filename or "sans-nom").split("/")[-1].split("\\")[-1][:255]
        # Une lecture bornée : un fichier surdimensionné n'occupe pas la mémoire.
        data = await upload.read(max_bytes + 1)
        await upload.close()
        if len(data) > max_bytes:
            rejected.append(
                {
                    "filename": display_name,
                    "reason": f"fichier de plus de {settings.HR_MAX_FILE_MB} Mo",
                }
            )
            continue
        if not data:
            rejected.append({"filename": display_name, "reason": "fichier vide"})
            continue
        # Le type réel prime sur l'extension et sur le Content-Type annoncé.
        kind = sniff_kind(data)
        if kind is None:
            rejected.append(
                {
                    "filename": display_name,
                    "reason": "type de fichier non autorisé (PDF ou DOCX attendu)",
                }
            )
            continue

        relative_path = store.save(org_id=ctx.org_id, job_id=job.id, data=data, kind=kind)
        candidate = Candidate(
            organization_id=ctx.org_id,
            job_id=job.id,
            file_path=relative_path,
            original_filename=display_name,
            mime=ALLOWED_KINDS[kind][1],
            size_bytes=len(data),
            status=CANDIDATE_UPLOADED,
        )
        ctx.session.add(candidate)
        await ctx.session.flush()
        await ctx.session.refresh(candidate)
        accepted.append(_candidate_out(candidate))

    # Données personnelles : on journalise des compteurs, jamais les noms.
    logger.info(
        "hr_candidates_uploaded",
        job_id=str(job.id),
        accepted=len(accepted),
        rejected=len(rejected),
    )
    return {"job_id": str(job.id), "accepted": accepted, "rejected": rejected}


@router.delete("/jobs/{job_id}/candidates/{candidate_id}", status_code=204)
async def delete_candidate(
    job_id: uuid.UUID, candidate_id: uuid.UUID, ctx: HRContext, store: Store
) -> None:
    """Retrait d'une candidature : la ligne ET le fichier.

    Un CV est une donnée personnelle : le supprimer de l'écran doit le
    supprimer du disque. Le fichier part en premier ; si l'effacement échoue,
    la ligne reste et l'appel remonte l'erreur, plutôt que de laisser un
    fichier orphelin qu'aucune interface ne sait plus retrouver.
    """
    await _get_job(ctx, job_id)
    candidate = await ctx.session.get(Candidate, candidate_id)
    if candidate is None or candidate.job_id != job_id:
        raise HTTPException(status_code=404, detail="Candidature introuvable")
    store.delete(candidate.file_path)
    await ctx.session.delete(candidate)
    logger.info("hr_candidate_deleted", job_id=str(job_id))


@router.get("/jobs/{job_id}/candidates")
async def list_candidates(
    job_id: uuid.UUID, ctx: HRContext, limit: int = 100
) -> list[dict[str, Any]]:
    await _get_job(ctx, job_id)
    rows = (
        (
            await ctx.session.execute(
                select(Candidate)
                .where(Candidate.job_id == job_id)
                .order_by(Candidate.created_at)
                .limit(min(limit, 500))
            )
        )
        .scalars()
        .all()
    )
    return [_candidate_out(row) for row in rows]
