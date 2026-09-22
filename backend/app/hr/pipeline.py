"""Cœur du pipeline de présélection, en asynchrone et hors Celery.

Les tâches Celery (`app/hr/tasks.py`) ne sont que des enveloppes : toute la
logique vit ici, ce qui la rend testable sans courtier de messages et
réutilisable depuis un script de mesure.

Chaîne par CV (ADR-007 : chaque candidature est traitée SEULE) :

    extraction du texte  ->  profil structuré  ->  notation contre la grille

Trois états d'arrêt possibles pour une candidature, tous explicites :
`needs_ocr` (document sans texte), `error` (fichier illisible ou étape en
échec), `scored`. Un échec ne fait jamais tomber le lot.
"""

import json
import time
import uuid
from datetime import UTC, datetime
from typing import Any

import structlog
from sqlalchemy import func, select

from app.core.llm import CallContext, LLMGateway, get_gateway, load_prompt
from app.core.models import LLMCall
from app.core.tenant import tenant_session
from app.hr.criteria import Criteria
from app.hr.extraction import ExtractionError, NeedsOCR, extract_text
from app.hr.models import (
    CANDIDATE_ERROR,
    CANDIDATE_EXTRACTED,
    CANDIDATE_NEEDS_OCR,
    RUN_DONE,
    SCORE_FAILED,
    SCORE_SCORED,
    Candidate,
    CandidateScore,
    Job,
    ScreeningRun,
)
from app.hr.schemas import (
    Calibration,
    CandidateAssessment,
    CandidateProfile,
    align_with_grid,
    compute_overall,
)
from app.hr.stats import clear as clear_stats
from app.hr.stats import collect as collect_stats
from app.hr.stats import record_failure, record_step

logger = structlog.get_logger(__name__)

PROFILE_PROMPT = "hr.profile"
PROFILE_ALIAS = "hr.extract"
SCORE_PROMPT = "hr.score"
SCORE_ALIAS = "hr.score"

# Délimiteurs du bloc contenant le CV. Le texte du candidat est une DONNÉE :
# toute tentative de refermer le bloc est neutralisée avant insertion.
OPEN_DELIMITER = "<<<CV"
CLOSE_DELIMITER = "CV>>>"


def wrap_cv(text: str, instruction: str) -> str:
    """Message utilisateur : consigne hors du bloc, CV dedans."""
    safe = text.replace(OPEN_DELIMITER, "").replace(CLOSE_DELIMITER, "")
    return f"{instruction}\n{OPEN_DELIMITER}\n{safe}\n{CLOSE_DELIMITER}"


def grid_instruction(grid: Criteria) -> str:
    """Grille rendue en texte, poids et caractère éliminatoire compris."""
    lignes = [
        f"- {c.name} (poids {c.weight_1_5}/5"
        + (", ÉLIMINATOIRE" if c.must_have else "")
        + f") : {c.description}"
        for c in grid.criteria
    ]
    return "Évalue ce CV face à la grille suivante, critère par critère :\n" + "\n".join(lignes)


# --- étapes ---------------------------------------------------------------


async def run_extraction(
    org_id: uuid.UUID, run_id: uuid.UUID, candidate_id: uuid.UUID, store: Any
) -> str | None:
    """Étape 1 : texte du CV. Renvoie None si la candidature s'arrête ici."""
    started = time.monotonic()
    async with tenant_session(org_id) as session:
        candidate = await session.get(Candidate, candidate_id)
        if candidate is None:
            return None
        if candidate.extracted_text:  # déjà extrait : rejeu sans surcoût
            return candidate.extracted_text
        kind = "pdf" if candidate.mime.endswith("pdf") else "docx"
        try:
            with store.open(candidate.file_path) as handle:
                data = handle.read()
            text = extract_text(data, kind)
        except NeedsOCR as exc:
            candidate.status = CANDIDATE_NEEDS_OCR
            candidate.profile_json = {"error": str(exc)}
            return None
        except (ExtractionError, OSError, ValueError) as exc:
            candidate.status = CANDIDATE_ERROR
            candidate.profile_json = {"error": f"{type(exc).__name__}: {exc}"}
            return None
        candidate.extracted_text = text
        candidate.status = CANDIDATE_EXTRACTED
    record_step(run_id, "extract", time.monotonic() - started)
    return text


async def run_profile(
    org_id: uuid.UUID,
    run_id: uuid.UUID,
    candidate_id: uuid.UUID,
    text: str,
    gateway: LLMGateway | None = None,
) -> CandidateProfile | None:
    """Étape 2 : profil structuré, neutre vis-à-vis de l'offre."""
    started = time.monotonic()
    system, version = load_prompt(PROFILE_PROMPT)
    result = await (gateway or get_gateway()).complete(
        PROFILE_ALIAS,
        [
            {"role": "system", "content": system},
            {
                "role": "user",
                "content": wrap_cv(text, "Structure le CV suivant."),
            },
        ],
        # La trace d'un run EST son identifiant : le coût et les jetons de la
        # campagne se relisent ensuite dans llm_calls par trace_id.
        ctx=CallContext(
            org_id=org_id, agent=PROFILE_PROMPT, prompt_version=version, trace_id=run_id
        ),
        response_model=CandidateProfile,
    )
    if not isinstance(result.parsed, CandidateProfile):
        return None
    async with tenant_session(org_id) as session:
        candidate = await session.get(Candidate, candidate_id)
        if candidate is not None:
            candidate.profile_json = result.parsed.model_dump(mode="json")
    record_step(run_id, "profile", time.monotonic() - started)
    return result.parsed


async def run_scoring(
    org_id: uuid.UUID,
    run_id: uuid.UUID,
    candidate_id: uuid.UUID,
    text: str,
    grid: Criteria,
    profile: CandidateProfile | None,
    gateway: LLMGateway | None = None,
) -> dict[str, Any]:
    """Étape 3 : notation contre la grille validée, puis note calculée en code."""
    started = time.monotonic()
    system, version = load_prompt(SCORE_PROMPT)
    instruction = grid_instruction(grid)
    if profile is not None:
        instruction += (
            "\n\nProfil déjà structuré à partir de ce CV (aide à la lecture, "
            "le CV reste la seule source de preuve) :\n"
            + profile.model_dump_json(exclude_none=True)
        )
    result = await (gateway or get_gateway()).complete(
        SCORE_ALIAS,
        [
            {"role": "system", "content": system},
            {"role": "user", "content": wrap_cv(text, instruction)},
        ],
        ctx=CallContext(org_id=org_id, agent=SCORE_PROMPT, prompt_version=version, trace_id=run_id),
        response_model=CandidateAssessment,
    )
    if not isinstance(result.parsed, CandidateAssessment):
        raise ValueError("Le modèle n'a pas produit d'évaluation exploitable")

    # La grille du RH fait foi, pas ce que le modèle a bien voulu renvoyer.
    lignes, rates = align_with_grid(result.parsed, grid.weights(), grid.must_haves())
    overall = compute_overall(lignes, rates)
    score_json = {
        "criteria": lignes,
        "must_have_failed": rates,
        "strengths": result.parsed.strengths,
        "concerns": result.parsed.concerns,
        "confidence": result.parsed.confidence,
        "prompt_version": version,
    }
    await _persist_score(org_id, run_id, candidate_id, score_json, overall)
    record_step(run_id, "score", time.monotonic() - started)
    return {"overall": overall, "must_have_failed": rates}


async def _persist_score(
    org_id: uuid.UUID,
    run_id: uuid.UUID,
    candidate_id: uuid.UUID,
    score_json: dict[str, Any],
    overall: int,
) -> None:
    """Écriture idempotente : une seule ligne par (run, candidat).

    Un rejeu de tâche — retry Celery, message livré deux fois — met à jour la
    ligne existante au lieu d'en créer une seconde. La contrainte d'unicité en
    base ferme le cas de la course entre deux workers.
    """
    async with tenant_session(org_id) as session:
        existing = (
            await session.execute(
                select(CandidateScore).where(
                    CandidateScore.run_id == run_id,
                    CandidateScore.candidate_id == candidate_id,
                )
            )
        ).scalar_one_or_none()
        if existing is None:
            session.add(
                CandidateScore(
                    organization_id=org_id,
                    run_id=run_id,
                    candidate_id=candidate_id,
                    score_json=score_json,
                    overall=overall,
                    status=SCORE_SCORED,
                )
            )
        else:
            existing.score_json = score_json
            existing.overall = overall
            existing.status = SCORE_SCORED
            existing.error = None


async def mark_failed(
    org_id: uuid.UUID, run_id: uuid.UUID, candidate_id: uuid.UUID, reason: str, step: str
) -> None:
    """Une candidature sort du lot avec un motif — le lot, lui, continue."""
    record_failure(run_id, step)
    async with tenant_session(org_id) as session:
        existing = (
            await session.execute(
                select(CandidateScore).where(
                    CandidateScore.run_id == run_id,
                    CandidateScore.candidate_id == candidate_id,
                )
            )
        ).scalar_one_or_none()
        if existing is None:
            session.add(
                CandidateScore(
                    organization_id=org_id,
                    run_id=run_id,
                    candidate_id=candidate_id,
                    score_json=None,
                    overall=None,
                    status=SCORE_FAILED,
                    error=reason[:500],
                )
            )
        elif existing.status != SCORE_SCORED:  # ne jamais écraser un succès
            existing.status = SCORE_FAILED
            existing.error = reason[:500]


async def load_grid(org_id: uuid.UUID, run_id: uuid.UUID) -> Criteria:
    """Grille validée de l'offre du run. La notation ne part jamais sans."""
    async with tenant_session(org_id) as session:
        run = await session.get(ScreeningRun, run_id)
        if run is None:
            raise ValueError(f"Campagne {run_id} introuvable")
        job = await session.get(Job, run.job_id)
        if job is None or not job.criteria_json:
            raise ValueError("Offre sans grille de critères validée")
        return Criteria.model_validate(job.criteria_json)


async def already_scored(org_id: uuid.UUID, run_id: uuid.UUID, candidate_id: uuid.UUID) -> bool:
    """Notation déjà faite pour ce couple ? Garde d'idempotence du rejeu."""
    async with tenant_session(org_id) as session:
        row = (
            await session.execute(
                select(CandidateScore.status).where(
                    CandidateScore.run_id == run_id,
                    CandidateScore.candidate_id == candidate_id,
                )
            )
        ).scalar_one_or_none()
    return row == SCORE_SCORED


async def load_text(org_id: uuid.UUID, candidate_id: uuid.UUID) -> str | None:
    async with tenant_session(org_id) as session:
        candidate = await session.get(Candidate, candidate_id)
        return candidate.extracted_text if candidate else None


async def finalize_run(org_id: uuid.UUID, run_id: uuid.UUID) -> dict[str, Any]:
    """Classement, compteurs et durées : la campagne est close.

    Le classement se calcule depuis la BASE, jamais depuis les retours des
    tâches : si l'une a été rejouée, seul l'état persisté fait foi. À notes
    égales, la confiance du modèle départage, puis l'ordre de dépôt — un
    classement doit être reproductible, pas dépendant de l'ordre d'arrivée
    des messages.
    """
    async with tenant_session(org_id) as session:
        run = await session.get(ScreeningRun, run_id)
        if run is None:
            raise ValueError(f"Campagne {run_id} introuvable")
        scores = (
            (await session.execute(select(CandidateScore).where(CandidateScore.run_id == run_id)))
            .scalars()
            .all()
        )
        classes = sorted(
            (s for s in scores if s.status == SCORE_SCORED),
            key=lambda s: (
                -(s.overall or 0),
                -float((s.score_json or {}).get("confidence") or 0),
                str(s.candidate_id),
            ),
        )
        for position, score in enumerate(classes, start=1):
            score.rank = position
        echecs = [s for s in scores if s.status != SCORE_SCORED]
        for score in echecs:
            score.rank = None

        counters = collect_stats(run_id)
        cost, tokens, calls = await _llm_usage(session, run_id)
        total = len(scores)
        run.stats_json = {
            "candidates": total,
            "scored": len(classes),
            "failed": len(echecs),
            "steps": {
                step: {
                    "count": int(counters.get(f"{step}_count", 0)),
                    "total_seconds": round(counters.get(f"{step}_seconds", 0.0), 2),
                    "mean_seconds": round(
                        counters.get(f"{step}_seconds", 0.0)
                        / max(1, int(counters.get(f"{step}_count", 0))),
                        3,
                    ),
                }
                for step in ("extract", "profile", "score")
            },
            "failures_by_step": {
                step: int(counters.get(f"failed_{step}", 0)) for step in ("extract", "score")
            },
            "llm": {"calls": calls, "tokens": tokens, "cost_usd": cost},
            "seconds_per_candidate": round(
                sum(counters.get(f"{s}_seconds", 0.0) for s in ("extract", "profile", "score"))
                / max(1, total),
                2,
            ),
        }
        run.status = RUN_DONE
        run.finished_at = datetime.now(UTC)
        summary = {"candidates": total, "scored": len(classes), "failed": len(echecs)}
    clear_stats(run_id)
    return summary


async def _llm_usage(session: Any, run_id: uuid.UUID) -> tuple[float, int, int]:
    """Coût, jetons et nombre d'appels de la campagne, relus dans `llm_calls`.

    La trace d'un run vaut son identifiant : une seule source de vérité pour
    le coût, celle qui sert déjà la page Usage.
    """
    row = (
        await session.execute(
            select(
                func.coalesce(func.sum(LLMCall.cost_usd), 0),
                func.coalesce(func.sum(LLMCall.input_tokens + LLMCall.output_tokens), 0),
                func.count(),
            ).where(LLMCall.trace_id == run_id)
        )
    ).one()
    return float(row[0]), int(row[1]), int(row[2])


CALIBRATE_PROMPT = "hr.calibrate"
CALIBRATE_ALIAS = "hr.calibrate"


async def run_calibration(
    org_id: uuid.UUID,
    run_id: uuid.UUID,
    top_k: int,
    gateway: LLMGateway | None = None,
) -> dict[str, Any]:
    """Passe comparative sur les K premiers (option écartée par défaut, ADR-007).

    La notation par CV indépendant garantit l'égalité de traitement mais rend
    les écarts fins peu fiables : entre 78 et 76, l'ordre relève du bruit. Ce
    second regard ne voit QUE les K premiers, ne modifie AUCUNE note, et ne
    touche qu'au rang. L'ordre d'origine est conservé dans le résultat pour
    que la comparaison soit mesurable au chapitre 8.
    """
    async with tenant_session(org_id) as session:
        tetes = (
            (
                await session.execute(
                    select(CandidateScore)
                    .where(CandidateScore.run_id == run_id, CandidateScore.status == SCORE_SCORED)
                    .order_by(CandidateScore.rank)
                    .limit(top_k)
                )
            )
            .scalars()
            .all()
        )
        if len(tetes) < 2:
            return {"calibrated": 0, "changed": False}
        resume = [
            {
                "candidate_id": str(s.candidate_id),
                "overall": s.overall,
                "must_have_failed": (s.score_json or {}).get("must_have_failed", []),
                "criteria": [
                    {
                        "name": c.get("name"),
                        "score_0_5": c.get("score_0_5"),
                        "evidence": c.get("evidence"),
                    }
                    for c in (s.score_json or {}).get("criteria", [])
                ],
            }
            for s in tetes
        ]
        ordre_initial = [str(s.candidate_id) for s in tetes]

    system, version = load_prompt(CALIBRATE_PROMPT)
    result = await (gateway or get_gateway()).complete(
        CALIBRATE_ALIAS,
        [
            {"role": "system", "content": system},
            {
                "role": "user",
                "content": (
                    "Départage ces candidats, déjà notés individuellement "
                    "contre la même grille :\n" + json.dumps(resume, ensure_ascii=False)
                ),
            },
        ],
        ctx=CallContext(
            org_id=org_id, agent=CALIBRATE_PROMPT, prompt_version=version, trace_id=run_id
        ),
        response_model=Calibration,
    )
    if not isinstance(result.parsed, Calibration) or result.parsed.unchanged:
        return {"calibrated": len(tetes), "changed": False}

    # Le modèle ne peut ni ajouter, ni retirer un candidat du top-K : on ne
    # garde que les identifiants connus, et on complète avec l'ordre initial.
    connus = set(ordre_initial)
    nouvel_ordre = [e.candidate_id for e in result.parsed.ordering if e.candidate_id in connus]
    nouvel_ordre += [cid for cid in ordre_initial if cid not in nouvel_ordre]
    if nouvel_ordre == ordre_initial:
        return {"calibrated": len(tetes), "changed": False}

    raisons = {e.candidate_id: e.rationale for e in result.parsed.ordering}
    async with tenant_session(org_id) as session:
        for position, candidate_id in enumerate(nouvel_ordre, start=1):
            score = (
                await session.execute(
                    select(CandidateScore).where(
                        CandidateScore.run_id == run_id,
                        CandidateScore.candidate_id == uuid.UUID(candidate_id),
                    )
                )
            ).scalar_one()
            detail = dict(score.score_json or {})
            detail["rank_before_calibration"] = score.rank
            detail["calibration_rationale"] = raisons.get(candidate_id)
            score.score_json = detail
            score.rank = position
    return {"calibrated": len(tetes), "changed": True}
