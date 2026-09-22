"""Endpoints des campagnes de présélection : lancer, suivre, consulter.

L'API ne fait jamais l'analyse : elle crée la campagne, publie les tâches et
rend la main (section NE PAS de la carte). Le suivi se lit ensuite en base,
ce qui rend la progression consultable depuis n'importe quel navigateur, même
après un rechargement ou une déconnexion.
"""

import uuid
from datetime import UTC, datetime
from typing import Annotated, Any

import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy import func, select

from app.auth.deps import RequestContext as AuthContext
from app.auth.deps import require_role
from app.hr.jobs import ensure_ready
from app.hr.models import (
    CANDIDATE_ERROR,
    CANDIDATE_UPLOADED,
    RUN_QUEUED,
    RUN_RUNNING,
    SCORE_SCORED,
    Candidate,
    CandidateScore,
    Job,
    ScreeningRun,
)
from app.hr.tasks import dispatch_candidate, dispatch_run

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/hr", tags=["hr"])

HRContext = Annotated[AuthContext, Depends(require_role("owner", "admin", "hr"))]


async def _get_run(ctx: AuthContext, run_id: uuid.UUID) -> ScreeningRun:
    """Le RLS rend invisibles les campagnes des autres organisations : 404."""
    run = await ctx.session.get(ScreeningRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Campagne introuvable")
    return run


@router.get("/jobs/{job_id}/runs")
async def list_runs(job_id: uuid.UUID, ctx: HRContext, limit: int = 20) -> list[dict[str, Any]]:
    """Campagnes d'une offre, la plus récente en tête.

    La liste des offres affiche « dernier run » : sans cette route, l'interface
    devrait deviner un identifiant de campagne ou en relancer une.
    """
    runs = (
        (
            await ctx.session.execute(
                select(ScreeningRun)
                .where(ScreeningRun.job_id == job_id)
                .order_by(ScreeningRun.created_at.desc())
                .limit(min(limit, 100))
            )
        )
        .scalars()
        .all()
    )
    return [
        {
            "run_id": str(run.id),
            "job_id": str(run.job_id),
            "status": run.status,
            "stats": run.stats_json,
            "created_at": run.created_at.isoformat() if run.created_at else None,
            "started_at": run.started_at.isoformat() if run.started_at else None,
            "finished_at": run.finished_at.isoformat() if run.finished_at else None,
        }
        for run in runs
    ]


@router.post("/jobs/{job_id}/runs", status_code=202)
async def start_run(
    job_id: uuid.UUID, ctx: HRContext, background: BackgroundTasks
) -> dict[str, Any]:
    """Lance une campagne sur tous les CV déposés. Réponse immédiate (202)."""
    job = await ctx.session.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Offre introuvable")
    # La grille validée par un humain est la condition d'entrée (ADR-007).
    ensure_ready(job)

    candidate_ids = list(
        (
            await ctx.session.execute(
                select(Candidate.id)
                .where(Candidate.job_id == job_id, Candidate.status != CANDIDATE_ERROR)
                .order_by(Candidate.created_at)
            )
        )
        .scalars()
        .all()
    )
    if not candidate_ids:
        raise HTTPException(status_code=409, detail="Aucune candidature à analyser")

    run = ScreeningRun(
        organization_id=ctx.org_id,
        job_id=job_id,
        status=RUN_QUEUED,
        stats_json={"candidates": len(candidate_ids)},
    )
    ctx.session.add(run)
    await ctx.session.flush()
    await ctx.session.refresh(run)

    run.status = RUN_RUNNING
    run.started_at = datetime.now(UTC)
    # Publication APRÈS la réponse : les dépendances à `yield` sont refermées
    # — donc la transaction validée — avant que les tâches d'arrière-plan ne
    # s'exécutent. Sans cela, un worker rapide chercherait une campagne que la
    # base n'a pas encore vue. La requête, elle, ne bloque pas (section NE PAS).
    background.add_task(dispatch_run, run.id, ctx.org_id, candidate_ids)
    logger.info("hr_run_started", run_id=str(run.id), candidates=len(candidate_ids))
    return {
        "run_id": str(run.id),
        "job_id": str(job_id),
        "status": RUN_RUNNING,
        "candidates": len(candidate_ids),
    }


@router.get("/runs/{run_id}")
async def get_run(run_id: uuid.UUID, ctx: HRContext) -> dict[str, Any]:
    """Progression de la campagne et état de chaque candidature."""
    run = await _get_run(ctx, run_id)
    attendus = (
        (
            await ctx.session.execute(
                select(Candidate.id, Candidate.original_filename, Candidate.status).where(
                    Candidate.job_id == run.job_id
                )
            )
        )
        .tuples()
        .all()
    )
    resultats = {
        row.candidate_id: row
        for row in (
            await ctx.session.execute(select(CandidateScore).where(CandidateScore.run_id == run_id))
        )
        .scalars()
        .all()
    }
    par_cv = []
    for cid, filename, statut_cv in attendus:
        score = resultats.get(cid)
        par_cv.append(
            {
                "candidate_id": str(cid),
                "original_filename": filename,
                # Tant qu'aucune ligne de résultat n'existe, la candidature
                # est en attente : le pipeline ne l'a pas encore atteinte.
                "status": score.status if score else "pending",
                "overall": score.overall if score else None,
                "error": score.error if score else None,
                "file_status": statut_cv,
            }
        )
    termines = sum(1 for x in par_cv if x["status"] != "pending")
    return {
        "run_id": str(run.id),
        "job_id": str(run.job_id),
        "status": run.status,
        "total": len(par_cv),
        "done": termines,
        "progress": round(termines / len(par_cv), 3) if par_cv else 0.0,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "finished_at": run.finished_at.isoformat() if run.finished_at else None,
        "stats": run.stats_json,
        "candidates": par_cv,
    }


@router.post("/runs/{run_id}/candidates/{candidate_id}/retry", status_code=202)
async def retry_candidate(
    run_id: uuid.UUID,
    candidate_id: uuid.UUID,
    ctx: HRContext,
    background: BackgroundTasks,
) -> dict[str, Any]:
    """Reprend un CV en échec sans relancer toute la campagne.

    Un CV illisible, un quota fournisseur atteint au mauvais moment : le lot a
    survécu, mais ce CV n'a pas de note. On efface sa ligne de résultat pour
    que l'étape de notation ne se croie pas déjà faite (`already_scored`), on
    remet la candidature en `uploaded` et on relance sa chaîne. Le classement
    est recalculé à la fin de la reprise.
    """
    run = await _get_run(ctx, run_id)
    candidate = await ctx.session.get(Candidate, candidate_id)
    if candidate is None or candidate.job_id != run.job_id:
        raise HTTPException(status_code=404, detail="Candidature introuvable")

    score = (
        await ctx.session.execute(
            select(CandidateScore).where(
                CandidateScore.run_id == run_id,
                CandidateScore.candidate_id == candidate_id,
            )
        )
    ).scalar_one_or_none()
    if score is not None:
        if score.status == SCORE_SCORED:
            raise HTTPException(status_code=409, detail="Cette candidature est déjà notée")
        await ctx.session.delete(score)

    # Le texte extrait est conservé : si l'extraction avait réussi, la reprise
    # ne redemande pas le fichier. C'est le motif d'échec qui est effacé.
    candidate.status = CANDIDATE_UPLOADED
    run.status = RUN_RUNNING
    run.finished_at = None
    background.add_task(dispatch_candidate, run_id, ctx.org_id, candidate_id)
    logger.info("hr_candidate_retried", run_id=str(run_id))
    return {"run_id": str(run_id), "candidate_id": str(candidate_id), "status": "queued"}


def _ligne(
    score: CandidateScore, fiches: dict[uuid.UUID, tuple[str | None, dict[str, Any]]]
) -> dict[str, Any]:
    """Une ligne de classement : la note, le profil et le détail par critère."""
    _, profil = fiches.get(score.candidate_id, (None, {}))
    return {
        "rank": score.rank,
        "candidate_id": str(score.candidate_id),
        "original_filename": fiches.get(score.candidate_id, (None, {}))[0],
        "headline": profil.get("headline"),
        "years_experience": profil.get("years_experience"),
        "skills": profil.get("skills", [])[:8],
        "overall": score.overall,
        "status": score.status,
        "error": score.error,
        **(score.score_json or {}),
    }


@router.get("/runs/{run_id}/results")
async def get_results(
    run_id: uuid.UUID,
    ctx: HRContext,
    limit: int = 20,
    offset: int = 0,
    min_score: Annotated[int, Query(ge=0, le=100, description="Note minimale")] = 0,
    must_have_only: Annotated[
        bool, Query(description="Ne garder que les CV qui tiennent tous les éliminatoires")
    ] = False,
    q: Annotated[str | None, Query(description="Recherche sur le nom de fichier")] = None,
) -> dict[str, Any]:
    """Classement final, avec le détail par critère et les preuves citées.

    Paginé et filtré côté serveur : la cible est 500 CV par lot (carte
    Architecture macro), et un filtre appliqué à la seule page affichée
    donnerait un classement faux.

    Les CV en échec ne sont JAMAIS renvoyés dans le classement filtré : ils
    sortent à part (`failed`), parce qu'un échec est précisément ce qui
    demande une action humaine — le masquer derrière un filtre de note, c'est
    le perdre.
    """
    run = await _get_run(ctx, run_id)

    noms_recherches: set[uuid.UUID] | None = None
    if q:
        motif = f"%{q.strip()}%"
        noms_recherches = {
            cid
            for (cid,) in (
                await ctx.session.execute(
                    select(Candidate.id).where(
                        Candidate.job_id == run.job_id,
                        Candidate.original_filename.ilike(motif),
                    )
                )
            ).all()
        }

    filtres = [
        CandidateScore.run_id == run_id,
        CandidateScore.status == SCORE_SCORED,
        func.coalesce(CandidateScore.overall, 0) >= min_score,
    ]
    if must_have_only:
        filtres.append(
            func.coalesce(func.jsonb_array_length(CandidateScore.score_json["must_have_failed"]), 0)
            == 0
        )
    if noms_recherches is not None:
        filtres.append(CandidateScore.candidate_id.in_(noms_recherches or {uuid.UUID(int=0)}))

    total = (
        await ctx.session.execute(select(func.count()).select_from(CandidateScore).where(*filtres))
    ).scalar_one()
    scores = (
        (
            await ctx.session.execute(
                select(CandidateScore)
                .where(*filtres)
                .order_by(CandidateScore.rank.nulls_last(), CandidateScore.overall.desc())
                .offset(max(offset, 0))
                .limit(min(max(limit, 1), 500))
            )
        )
        .scalars()
        .all()
    )
    echecs = (
        (
            await ctx.session.execute(
                select(CandidateScore).where(
                    CandidateScore.run_id == run_id,
                    CandidateScore.status != SCORE_SCORED,
                )
            )
        )
        .scalars()
        .all()
    )
    # Le profil sert le résumé affiché sur chaque carte du classement : sans
    # lui, l'interface devrait inventer une accroche à partir des notes.
    fiches = {
        cid: (nom, profil or {})
        for cid, nom, profil in (
            (
                await ctx.session.execute(
                    select(Candidate.id, Candidate.original_filename, Candidate.profile_json).where(
                        Candidate.job_id == run.job_id
                    )
                )
            )
            .tuples()
            .all()
        )
    }
    return {
        "run_id": str(run.id),
        "status": run.status,
        "stats": run.stats_json,
        "ranking": [_ligne(s, fiches) for s in scores],
        "failed": [_ligne(s, fiches) for s in echecs],
        "total": total,
    }
