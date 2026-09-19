"""GET /usage — agrégat tokens/coût LLM de l'organisation COURANTE.

Module transverse volontairement HORS de core/ : il dépend du contexte
d'authentification (app.auth.deps), que core ne doit jamais importer.
Le périmètre org est garanti deux fois : session RLS du contexte de requête
+ politique tenant_isolation_llm_calls.
"""

from decimal import Decimal
from typing import Any

from fastapi import APIRouter
from sqlalchemy import func, select

from app.auth.deps import Context
from app.core.models import LLMCall

router = APIRouter(tags=["usage"])


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
