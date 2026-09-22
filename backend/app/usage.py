"""Usage LLM de l'organisation COURANTE : coût, jetons, latence, appels.

Module transverse volontairement HORS de core/ : il dépend du contexte
d'authentification (app.auth.deps), que core ne doit jamais importer.
Le périmètre org est garanti deux fois : session RLS du contexte de requête
+ politique tenant_isolation_llm_calls.

Deux règles de cet écran.

**Réservé à l'encadrement** (owner, admin) : c'est une information budgétaire,
pas un outil de travail de l'équipe.

**Jamais le contenu des prompts** (carte, section NE PAS). La table `llm_calls`
ne stocke que des métadonnées ; rien ici n'expose un message envoyé au modèle,
ce qui interdirait aussi de faire fuiter un CV ou un compte rendu d'appel.
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from sqlalchemy import Date, cast, func, select

from app.auth.deps import RequestContext, require_role
from app.core.models import LLMCall

router = APIRouter(tags=["usage"])

# L'usage est une information budgétaire : owner et admin, pas l'équipe.
Context = Annotated[RequestContext, Depends(require_role("owner", "admin"))]

# Bornes des fenêtres demandées, pour qu'un paramètre d'URL ne déclenche pas
# une agrégation sur toute l'histoire de la table.
MAX_JOURS = 180
MAX_APPELS = 200


@router.get("/usage")
async def usage(ctx: Context) -> dict[str, Any]:
    rows = (
        await ctx.session.execute(
            select(
                LLMCall.alias,
                func.count().label("calls"),
                func.coalesce(func.sum(LLMCall.input_tokens), 0).label("input_tokens"),
                func.coalesce(func.sum(LLMCall.output_tokens), 0).label("output_tokens"),
                func.coalesce(func.sum(LLMCall.cost_usd), Decimal(0)).label("cost_usd"),
            )
            .group_by(LLMCall.alias)
            .order_by(LLMCall.alias)
        )
    ).all()

    by_alias = [
        {
            "alias": r.alias,
            "calls": r.calls,
            "input_tokens": r.input_tokens,
            "output_tokens": r.output_tokens,
            "cost_usd": float(r.cost_usd),
        }
        for r in rows
    ]
    return {
        "organization_id": str(ctx.org_id),
        "total_calls": sum(a["calls"] for a in by_alias),
        "input_tokens": sum(a["input_tokens"] for a in by_alias),
        "output_tokens": sum(a["output_tokens"] for a in by_alias),
        "cost_usd": round(sum(a["cost_usd"] for a in by_alias), 6),
        "by_alias": by_alias,
    }


@router.get("/usage/daily")
async def daily(ctx: Context, days: int = 30) -> dict[str, Any]:
    """Coût et jetons par jour : la courbe du chapitre 8.

    Les jours sans appel n'apparaissent pas : c'est à l'écran de combler les
    trous s'il veut une courbe continue, pas à la base d'inventer des zéros.
    """
    fenetre = max(1, min(days, MAX_JOURS))
    depuis = datetime.now(UTC) - timedelta(days=fenetre)
    jour = cast(LLMCall.created_at, Date).label("day")
    rows = (
        await ctx.session.execute(
            select(
                jour,
                func.count().label("calls"),
                func.coalesce(func.sum(LLMCall.input_tokens), 0).label("input_tokens"),
                func.coalesce(func.sum(LLMCall.output_tokens), 0).label("output_tokens"),
                func.coalesce(func.sum(LLMCall.cost_usd), Decimal(0)).label("cost_usd"),
            )
            .where(LLMCall.created_at >= depuis)
            .group_by(jour)
            .order_by(jour)
        )
    ).all()
    return {
        "days": fenetre,
        "series": [
            {
                "day": r.day.isoformat(),
                "calls": r.calls,
                "input_tokens": r.input_tokens,
                "output_tokens": r.output_tokens,
                "cost_usd": float(r.cost_usd),
            }
            for r in rows
        ],
    }


@router.get("/usage/by-agent")
async def by_agent(ctx: Context) -> dict[str, Any]:
    """Coût, jetons et latence par agent, puis par alias de modèle.

    Deux regroupements et non un seul : le mémoire compare les agents entre
    eux (qui coûte) et les alias entre eux (quel réglage coûte).
    """
    rows = (
        await ctx.session.execute(
            select(
                LLMCall.agent,
                LLMCall.alias,
                func.count().label("calls"),
                func.coalesce(func.sum(LLMCall.input_tokens), 0).label("input_tokens"),
                func.coalesce(func.sum(LLMCall.output_tokens), 0).label("output_tokens"),
                func.coalesce(func.sum(LLMCall.cost_usd), Decimal(0)).label("cost_usd"),
                func.avg(LLMCall.latency_ms).label("latency_ms"),
            )
            .group_by(LLMCall.agent, LLMCall.alias)
            .order_by(LLMCall.agent, LLMCall.alias)
        )
    ).all()
    detail = [
        {
            "agent": r.agent,
            "alias": r.alias,
            "calls": r.calls,
            "input_tokens": r.input_tokens,
            "output_tokens": r.output_tokens,
            "cost_usd": float(r.cost_usd),
            "latency_ms": int(r.latency_ms) if r.latency_ms is not None else None,
        }
        for r in rows
    ]
    par_agent: dict[str, dict[str, Any]] = {}
    for ligne in detail:
        agregat = par_agent.setdefault(
            ligne["agent"],
            {"agent": ligne["agent"], "calls": 0, "cost_usd": 0.0, "tokens": 0},
        )
        agregat["calls"] += ligne["calls"]
        agregat["cost_usd"] = round(agregat["cost_usd"] + ligne["cost_usd"], 6)
        agregat["tokens"] += ligne["input_tokens"] + ligne["output_tokens"]
    return {"by_agent": list(par_agent.values()), "by_agent_alias": detail}


@router.get("/usage/calls")
async def calls(ctx: Context, limit: int = 25, offset: int = 0) -> dict[str, Any]:
    """Derniers appels : agent, modèle, latence, coût. Jamais le prompt.

    Paginé côté serveur, comme la file : la table grandit à chaque appel de
    modèle. Le total accompagne la page.
    """
    total = (await ctx.session.execute(select(func.count()).select_from(LLMCall))).scalar_one()
    rows = (
        (
            await ctx.session.execute(
                select(LLMCall)
                .order_by(LLMCall.created_at.desc())
                .offset(max(offset, 0))
                .limit(min(max(limit, 1), MAX_APPELS))
            )
        )
        .scalars()
        .all()
    )
    return {
        "calls": [
            {
                "id": str(row.id),
                "agent": row.agent,
                "alias": row.alias,
                "model_used": row.model_used,
                "prompt_version": row.prompt_version,
                "input_tokens": row.input_tokens,
                "output_tokens": row.output_tokens,
                "latency_ms": row.latency_ms,
                "cost_usd": float(row.cost_usd) if row.cost_usd is not None else None,
                "status": row.status,
                "error": row.error,
                "created_at": row.created_at.isoformat(),
            }
            for row in rows
        ],
        "total": total,
    }
