"""Tests du runtime d'agent (critères carte runtime).

LLM simulé par un FakeGateway scripté (le vrai gateway a ses propres tests) ;
les traces `agent_traces` et l'historique s'écrivent dans la VRAIE base
(miara_app, RLS actif). Le prompt système est le vrai `prompts/echo/v1.md`.
"""

import json
import uuid
from typing import Any

from pydantic import BaseModel
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.auth.models import User
from app.core.agents import (
    AgentDefinition,
    Final,
    NeedsConfirmation,
    RequestContext,
    StepLimitExceeded,
    Tool,
    load_history,
    run,
    save_messages,
)
from app.core.llm import LLMResult
from app.core.models import AgentTrace


def _llm_text(content: str) -> LLMResult:
    return LLMResult(
        content=content,
        parsed=None,
        tool_calls=None,
        model_used="fake-model",
        input_tokens=10,
        output_tokens=5,
        latency_ms=3,
        cost_usd=None,
        trace_id=uuid.uuid4(),
    )


def _llm_tool(call_id: str, name: str, args: dict[str, Any]) -> LLMResult:
    result = _llm_text("")
    result.content = None
    result.tool_calls = [{"id": call_id, "name": name, "arguments": json.dumps(args)}]
    return result


class FakeGateway:
    def __init__(self, results: list[LLMResult]) -> None:
        self._results = list(results)
        self.calls: list[list[dict[str, Any]]] = []

    async def complete(self, alias: str, messages: Any, *, ctx: Any, **_: Any) -> LLMResult:
        self.calls.append([dict(m) for m in messages])
        return self._results.pop(0)


class _ReadArgs(BaseModel):
    text: str


class _WriteArgs(BaseModel):
    note: str


def _make_agent() -> tuple[AgentDefinition, dict[str, int]]:
    counts = {"read": 0, "write": 0}

    async def read_handler(args: BaseModel, ctx: RequestContext) -> dict[str, str]:
        assert isinstance(args, _ReadArgs)
        counts["read"] += 1
        return {"echo": args.text[::-1]}

    async def write_handler(args: BaseModel, ctx: RequestContext) -> dict[str, str]:
        assert isinstance(args, _WriteArgs)
        counts["write"] += 1
        return {"stored": args.note}

    definition = AgentDefinition(
        name="echo_test",
        model_alias="sales.route",
        prompt_name="echo",  # vrai prompt versionné du dépôt
        tools=[
            Tool("lire", "lecture fictive", _ReadArgs, False, read_handler),
            Tool("ecrire", "écriture fictive", _WriteArgs, True, write_handler),
        ],
    )
    return definition, counts


def _ctx(org_id: uuid.UUID) -> RequestContext:
    return RequestContext(org_id=org_id, user_id=uuid.uuid4(), role="sales")


async def _traces(
    admin_sessions: async_sessionmaker[AsyncSession], trace_id: uuid.UUID
) -> list[AgentTrace]:
    async with admin_sessions() as s:
        return list(
            (
                await s.execute(
                    select(AgentTrace)
                    .where(AgentTrace.trace_id == trace_id)
                    .order_by(AgentTrace.step)
                )
            )
            .scalars()
            .all()
        )


async def test_lecture_puis_reponse_finale_en_moins_de_3_etapes(
    two_orgs: tuple[uuid.UUID, uuid.UUID],
    admin_sessions: async_sessionmaker[AsyncSession],
) -> None:
    """Critères 1 et 5 : lecture -> résultat injecté -> finale ; trace lisible."""
    definition, counts = _make_agent()
    ctx = _ctx(two_orgs[0])
    gw = FakeGateway([_llm_tool("c1", "lire", {"text": "abc"}), _llm_text("Voilà : cba")])

    result = await run(definition, "inverse abc", ctx, gateway=gw)

    assert isinstance(result, Final)
    assert result.content == "Voilà : cba"
    assert counts["read"] == 1
    assert len(gw.calls) == 2  # ≤ 3 étapes
    # Le résultat de l'outil a bien été réinjecté avant le 2e appel LLM.
    tool_msgs = [m for m in gw.calls[1] if m["role"] == "tool"]
    assert tool_msgs and "cba" in tool_msgs[0]["content"]

    # Critère 5 : trace complète, ordonnée, lisible, par trace_id.
    traces = await _traces(admin_sessions, ctx.trace_id)
    assert [t.kind for t in traces] == ["llm_call", "tool_exec", "llm_call", "final"]
    assert [t.step for t in traces] == [1, 2, 3, 4]
    tool_exec = traces[1]
    assert tool_exec.tool == "lire"
    assert tool_exec.args_json == {"text": "abc"}
    assert tool_exec.result_summary is not None and "cba" in tool_exec.result_summary
    assert traces[0].latency_ms is not None


async def test_ecriture_needs_confirmation_puis_executee_une_seule_fois(
    two_orgs: tuple[uuid.UUID, uuid.UUID],
    admin_sessions: async_sessionmaker[AsyncSession],
) -> None:
    """Critère 2 : écriture -> NeedsConfirmation ; relance confirmée -> 1 exécution."""
    definition, counts = _make_agent()
    ctx = _ctx(two_orgs[0])

    first = await run(
        definition,
        "note ceci : hello",
        ctx,
        gateway=FakeGateway([_llm_tool("w1", "ecrire", {"note": "hello"})]),
    )
    assert isinstance(first, NeedsConfirmation)
    assert (first.call_id, first.tool, first.args) == ("w1", "ecrire", {"note": "hello"})
    assert counts["write"] == 0  # rien exécuté sans confirmation

    # Relance : même historique + confirmation. L'outil s'exécute UNE fois,
    # sans rappeler le LLM pour re-décider, puis le LLM conclut.
    gw2 = FakeGateway([_llm_text("C'est noté.")])
    second = await run(
        definition,
        None,
        ctx,
        history=first.new_messages,
        confirmations={"w1"},
        gateway=gw2,
    )
    assert isinstance(second, Final)
    assert counts["write"] == 1
    tool_msgs = [m for m in gw2.calls[0] if m["role"] == "tool"]
    assert tool_msgs and tool_msgs[0]["tool_call_id"] == "w1"

    kinds = [t.kind for t in await _traces(admin_sessions, ctx.trace_id)]
    assert "needs_confirmation" in kinds and "tool_exec" in kinds


async def test_args_invalides_renvoyes_au_modele_sans_execution(
    two_orgs: tuple[uuid.UUID, uuid.UUID],
    admin_sessions: async_sessionmaker[AsyncSession],
) -> None:
    """Critère 3 : args invalides -> erreur renvoyée au modèle, pas d'exécution."""
    definition, counts = _make_agent()
    ctx = _ctx(two_orgs[0])
    gw = FakeGateway([_llm_tool("c1", "lire", {"champ_inconnu": "x"}), _llm_text("Je corrige.")])

    result = await run(definition, "inverse", ctx, gateway=gw)

    assert isinstance(result, Final)
    assert counts["read"] == 0  # jamais exécuté
    tool_msgs = [m for m in gw.calls[1] if m["role"] == "tool"]
    assert tool_msgs and "Arguments invalides" in tool_msgs[0]["content"]
    kinds = [t.kind for t in await _traces(admin_sessions, ctx.trace_id)]
    assert "tool_error" in kinds and "tool_exec" not in kinds


async def test_boucle_infinie_step_limit_a_6(
    two_orgs: tuple[uuid.UUID, uuid.UUID],
    admin_sessions: async_sessionmaker[AsyncSession],
) -> None:
    """Critère 4 : le modèle boucle sur des outils -> StepLimitExceeded à 6."""
    definition, counts = _make_agent()
    ctx = _ctx(two_orgs[0])
    gw = FakeGateway([_llm_tool(f"c{i}", "lire", {"text": "x"}) for i in range(10)])

    result = await run(definition, "boucle", ctx, gateway=gw)

    assert isinstance(result, StepLimitExceeded)
    assert result.steps == 6
    assert len(gw.calls) == 6  # jamais un 7e appel LLM
    assert counts["read"] == 6
    assert (await _traces(admin_sessions, ctx.trace_id))[-1].kind == "step_limit"


async def test_historique_persiste_et_recharge(
    two_orgs: tuple[uuid.UUID, uuid.UUID],
    admin_sessions: async_sessionmaker[AsyncSession],
) -> None:
    """Tables conversations/messages : aller-retour fidèle, positions continues."""
    org_a, _ = two_orgs
    async with admin_sessions() as s, s.begin():
        user = User(
            email=f"agent-{uuid.uuid4().hex[:8]}@test.miara.dev",
            password_hash="x",
            full_name="Agent Tester",
        )
        s.add(user)
        await s.flush()
        user_id = user.id

    ctx = RequestContext(org_id=org_a, user_id=user_id, role="sales")
    batch1 = [
        {"role": "user", "content": "note hello"},
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": "w1",
                    "type": "function",
                    "function": {"name": "ecrire", "arguments": '{"note": "hello"}'},
                }
            ],
        },
    ]
    conv_id = await save_messages(ctx, "echo_test", batch1)
    await save_messages(
        ctx,
        "echo_test",
        [{"role": "tool", "tool_call_id": "w1", "content": '{"stored": "hello"}'}],
        conversation_id=conv_id,
    )

    history = await load_history(ctx, conv_id)
    assert [m["role"] for m in history] == ["user", "assistant", "tool"]
    assert history[1]["tool_calls"][0]["id"] == "w1"
    assert history[2]["tool_call_id"] == "w1"

    async with admin_sessions() as s, s.begin():
        await s.execute(delete(User).where(User.id == user_id))
