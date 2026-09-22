"""Endpoints du coach commercial : évaluer un texte, suivre la progression.

`POST /sales/coach` est un aller simple (pas une conversation) : un texte
entre, un `CoachingFeedback` structuré sort, et la session est enregistrée
pour la courbe de progression du commercial.

Journalisation dans le CRM (ADR-009) : c'est la PLATEFORME qui propose
l'écriture — le résumé et l'issue sont dérivés du retour du coach, pas
inventés par le modèle — et l'humain la confirme par un second appel explicite
(`POST /sales/coach/{id}/confirm`). Le modèle, lui, n'écrit jamais de
lui-même : s'il tente d'appeler l'outil d'écriture, la boucle le bloque et
l'endpoint refuse la réponse.
"""

import uuid
from typing import Annotated, Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from app.auth.deps import RequestContext as AuthContext
from app.auth.deps import require_role
from app.core.agents import Final, NeedsConfirmation, RequestContext, run
from app.core.llm import LLMGateway, gateway_dependency, load_prompt
from app.sales.agents.coach import (
    AGENT_NAME,
    CRITERIA,
    KINDS,
    CoachingFeedback,
    sales_coach,
    wrap_user_text,
)
from app.sales.models import CoachingSession
from app.sales.tools import log_call_note
from app.sales.tools.write import LogCallNoteArgs

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/sales", tags=["sales"])

CoachContext = Annotated[AuthContext, Depends(require_role("owner", "admin", "sales"))]
Gateway = Annotated[LLMGateway, Depends(gateway_dependency)]

MAX_TEXT_CHARS = 8000


class CoachRequest(BaseModel):
    text: str = Field(min_length=1, max_length=MAX_TEXT_CHARS)
    kind: str = Field(description=" | ".join(KINDS))
    account_id: str | None = Field(
        default=None, description="Compte ou opportunité Salesforce concerné"
    )
    log_to_crm: bool = Field(
        default=False, description="Proposer la journalisation du compte-rendu dans Salesforce"
    )


async def _pending_write_payload(
    session_id: uuid.UUID, args: LogCallNoteArgs, ctx: RequestContext
) -> dict[str, Any]:
    """Écriture proposée, telle qu'elle sera montrée à l'humain."""
    return {
        "tool": log_call_note.name,
        "args": args.model_dump(mode="json"),
        "preview": await log_call_note.render_preview(args, ctx),
        "confirm_url": f"/sales/coach/{session_id}/confirm",
    }


@router.post("/coach")
async def coach(body: CoachRequest, ctx: CoachContext, gateway: Gateway) -> dict[str, Any]:
    if body.kind not in KINDS:
        raise HTTPException(status_code=422, detail=f"kind attendu parmi : {', '.join(KINDS)}")
    if body.log_to_crm and not body.account_id:
        raise HTTPException(
            status_code=422, detail="account_id est requis pour journaliser dans Salesforce"
        )

    agent_ctx = RequestContext(org_id=ctx.org_id, user_id=ctx.user_id, role=ctx.role.value)
    result = await run(
        sales_coach,
        wrap_user_text(body.text, body.kind, body.account_id),
        agent_ctx,
        gateway=gateway,
    )

    if isinstance(result, NeedsConfirmation):
        # Le prompt l'interdit et la plateforme propose elle-même l'écriture :
        # si on passe ici, c'est un écart du modèle, pas un cas nominal.
        logger.warning("coach_ecriture_hors_procedure", tool=result.tool)
        raise HTTPException(status_code=409, detail="L'agent a proposé une écriture hors procédure")
    if not isinstance(result, Final) or not isinstance(result.structured, CoachingFeedback):
        raise HTTPException(
            status_code=502, detail="Le coach n'a pas produit d'évaluation exploitable"
        )

    feedback: CoachingFeedback = result.structured
    _, prompt_version = load_prompt(sales_coach.prompt_name)

    session = CoachingSession(
        organization_id=ctx.org_id,
        user_id=ctx.user_id,
        trace_id=result.trace_id,
        kind=body.kind,
        record_id=body.account_id,
        source_text=body.text,
        overall_0_100=feedback.overall_0_100,
        scores_json=feedback.scores(),
        feedback_json=feedback.model_dump(mode="json"),
        prompt_version=prompt_version,
    )
    ctx.session.add(session)
    await ctx.session.flush()

    pending: dict[str, Any] | None = None
    if body.log_to_crm and body.account_id:
        args = LogCallNoteArgs(
            record_id=body.account_id,
            summary=feedback.summary_line(),
            outcome=feedback.suggested_next_step,
        )
        pending = await _pending_write_payload(session.id, args, agent_ctx)
        session.pending_write_json = pending["args"]

    logger.info(
        "coach_session",
        session_id=str(session.id),
        kind=body.kind,
        overall=feedback.overall_0_100,
        trace_id=str(result.trace_id),
    )
    return {
        "session_id": str(session.id),
        "trace_id": str(result.trace_id),
        "prompt_version": prompt_version,
        "feedback": feedback.model_dump(mode="json"),
        "needs_confirmation": pending,
    }


@router.post("/coach/{session_id}/confirm")
async def confirm_log(session_id: uuid.UUID, ctx: CoachContext) -> dict[str, Any]:
    """Confirmation humaine de la journalisation proposée (ADR-009).

    Rejouable sans risque : la clé d'idempotence de l'outil d'écriture est
    dérivée de la session, pas d'un identifiant tiré au hasard.
    """
    session = await ctx.session.get(CoachingSession, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session de coaching introuvable")
    if session.pending_write_json is None:
        raise HTTPException(status_code=409, detail="Aucune écriture en attente sur cette session")

    args = LogCallNoteArgs.model_validate(session.pending_write_json)
    agent_ctx = RequestContext(
        org_id=ctx.org_id,
        user_id=ctx.user_id,
        role=ctx.role.value,
        trace_id=session.trace_id,
        call_id=f"coach:{session_id}",
    )
    result: dict[str, Any] = await log_call_note.run(args, agent_ctx)
    if "error" in result:
        return {"session_id": str(session_id), **result}

    session.sf_task_id = result.get("sf_record_id")
    session.pending_write_json = None
    return {"session_id": str(session_id), **result}


@router.get("/coach/sessions")
async def list_sessions(ctx: CoachContext, limit: int = 20) -> dict[str, Any]:
    """Progression du commercial : sessions récentes et moyennes par critère."""
    rows = (
        (
            await ctx.session.execute(
                select(CoachingSession)
                .where(CoachingSession.user_id == ctx.user_id)
                .order_by(CoachingSession.created_at.desc())
                .limit(min(limit, 100))
            )
        )
        .scalars()
        .all()
    )
    total, average = (
        await ctx.session.execute(
            select(func.count(), func.avg(CoachingSession.overall_0_100)).where(
                CoachingSession.user_id == ctx.user_id
            )
        )
    ).one()

    by_criterion: dict[str, float] = {}
    if rows:
        for name in CRITERIA:
            notes = [r.scores_json[name] for r in rows if name in r.scores_json]
            if notes:
                by_criterion[name] = round(sum(notes) / len(notes), 2)

    return {
        "agent": AGENT_NAME,
        "sessions": [
            {
                "id": str(r.id),
                "kind": r.kind,
                "record_id": r.record_id,
                "overall_0_100": r.overall_0_100,
                "scores": r.scores_json,
                "logged_task_id": r.sf_task_id,
                "created_at": r.created_at.isoformat(),
            }
            for r in rows
        ],
        "total_sessions": total,
        "average_overall": round(float(average), 1) if average is not None else None,
        "average_by_criterion": by_criterion,
    }
