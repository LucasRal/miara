"""Mesure de latence de l'agent commercial sur le jeu doré (hypothèse H3).

Exécute les questions de `scripts/data/golden_sales_v1.json` contre un CRM
RÉEL (l'org doit avoir une intégration Salesforce connectée), puis recoupe les
temps mesurés avec `llm_calls` et `agent_traces` — les deux sources de vérité
du chap. 8 du mémoire.

    uv run python -m scripts.bench_sales_assistant --org <uuid> [--limit N]

Lecture seule : le jeu doré ne contient aucune demande d'action, et une
écriture serait de toute façon bloquée par la confirmation humaine.
"""

import argparse
import asyncio
import json
import re
import statistics
import time
import uuid
from pathlib import Path
from typing import Any

from sqlalchemy import select, text

import app.db_registry  # noqa: F401  (enregistre tous les modèles : FK résolues)
from app.core.agents import Final, NeedsConfirmation, RequestContext, StepLimitExceeded, run
from app.core.llm import get_gateway
from app.core.models import AgentTrace, LLMCall
from app.core.tenant import tenant_session
from app.sales.agents.assistant import sales_assistant

GOLDEN_PATH = Path(__file__).resolve().parent / "data" / "golden_sales_v1.json"
# Identifiants Salesforce (15 ou 18 caractères) des objets que l'agent cite.
_SF_ID = re.compile(r"\b(001|003|006|500|00T|00U)[0-9A-Za-z]{12,15}\b")


async def first_member(org_id: uuid.UUID) -> uuid.UUID:
    """Un membre de l'org : le contexte d'agent exige un utilisateur réel
    (`app.current_user` des politiques RLS)."""
    async with tenant_session(org_id) as session:
        row = (
            await session.execute(
                text(
                    "SELECT user_id FROM memberships WHERE organization_id = :org "
                    "ORDER BY role LIMIT 1"
                ),
                {"org": str(org_id)},
            )
        ).first()
    if row is None:
        raise SystemExit(f"Aucun membre pour l'organisation {org_id}")
    return uuid.UUID(str(row[0]))


async def _flush_tool_cache(org_id: uuid.UUID) -> None:
    """Départ à froid : le cache d'outils (60 s) ne doit pas fausser le p95."""
    from app.sales.tools.cache import _PREFIX, _redis

    keys = [k async for k in _redis.scan_iter(f"{_PREFIX}{org_id}:*")]
    if keys:
        await _redis.delete(*keys)


async def _trace_breakdown(org_id: uuid.UUID, trace_id: uuid.UUID) -> dict[str, Any]:
    """Étapes et temps passés, relus depuis les tables de traçage."""
    async with tenant_session(org_id) as session:
        traces = (
            (
                await session.execute(
                    select(AgentTrace)
                    .where(AgentTrace.trace_id == trace_id)
                    .order_by(AgentTrace.step)
                )
            )
            .scalars()
            .all()
        )
        calls = (
            (await session.execute(select(LLMCall).where(LLMCall.trace_id == trace_id)))
            .scalars()
            .all()
        )
    return {
        "steps": len(traces),
        "llm_calls": len(calls),
        "llm_ms": sum(c.latency_ms for c in calls),
        "tools": [t.tool for t in traces if t.kind == "tool_exec"],
        "tool_ms": sum(t.latency_ms or 0 for t in traces if t.kind == "tool_exec"),
        "aliases": [c.alias for c in calls],
    }


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--org", required=True, help="UUID de l'organisation")
    parser.add_argument("--limit", type=int, default=0, help="n premières questions")
    parser.add_argument("--json", type=Path, help="écrit les mesures détaillées")
    args = parser.parse_args()

    org_id = uuid.UUID(args.org)
    user_id = await first_member(org_id)
    golden = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))["questions"]
    if args.limit:
        golden = golden[: args.limit]
    await _flush_tool_cache(org_id)

    gateway = get_gateway()
    rows: list[dict[str, Any]] = []
    for question in golden:
        ctx = RequestContext(org_id=org_id, user_id=user_id, role="sales")
        start = time.perf_counter()
        try:
            result = await run(sales_assistant, question["text"], ctx)
        except Exception as exc:  # une panne fournisseur ne doit pas tout perdre
            rows.append({**question, "error": f"{type(exc).__name__}: {exc}"})
            print(f"{question['id']} ERREUR {type(exc).__name__}: {exc}")
            continue
        elapsed_ms = (time.perf_counter() - start) * 1000
        await gateway.flush_logs()  # les lignes llm_calls sont écrites en arrière-plan

        content = result.content if isinstance(result, Final) else None
        outcome = {
            Final: "final",
            NeedsConfirmation: "needs_confirmation",
            StepLimitExceeded: "step_limit",
        }[type(result)]
        breakdown = await _trace_breakdown(org_id, result.trace_id)
        cited = bool(content and _SF_ID.search(content))
        rows.append(
            {
                **question,
                "outcome": outcome,
                "elapsed_ms": round(elapsed_ms),
                "cited_ids": cited,
                "content": content,
                **breakdown,
            }
        )
        print(
            f"{question['id']} {elapsed_ms:7.0f} ms  {outcome:<18} "
            f"llm={breakdown['llm_calls']} ({breakdown['llm_ms']} ms) "
            f"outils={','.join(breakdown['tools']) or '-'} ({breakdown['tool_ms']} ms) "
            f"ids={'oui' if cited else 'NON'}"
        )

    measured = [r for r in rows if "elapsed_ms" in r]
    if not measured:
        raise SystemExit("Aucune mesure exploitable.")
    latencies = sorted(float(r["elapsed_ms"]) for r in measured)
    p95 = latencies[max(0, round(0.95 * len(latencies)) - 1)]
    print("\n--- Jeu doré : latence de bout en bout ---")
    print(f"questions      : {len(measured)} / {len(rows)}")
    print(f"p50            : {statistics.median(latencies):.0f} ms")
    print(f"p95            : {p95:.0f} ms")
    print(f"max            : {latencies[-1]:.0f} ms")
    print(f"étapes (max)   : {max(r['steps'] for r in measured)}")
    print(f"appels LLM max : {max(r['llm_calls'] for r in measured)}")
    print(f"ids cités      : {sum(1 for r in measured if r['cited_ids'])} / {len(measured)}")
    print(f"réponses finales: {sum(1 for r in measured if r['outcome'] == 'final')}")
    if args.json:
        args.json.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"détail écrit dans {args.json}")


if __name__ == "__main__":
    asyncio.run(main())
