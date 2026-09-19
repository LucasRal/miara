"""Tests de la passerelle LLM (critères carte CORE passerelle).

Fournisseur simulé via `mock_response` de litellm : aucune clé API, aucun
réseau. La journalisation, elle, écrit dans la VRAIE table `llm_calls`
(rôle miara_app, RLS actif).
"""

import uuid
from typing import Any

import litellm
import pytest
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.llm import CallContext, LLMGateway, StructuredOutputError, UnknownAliasError
from app.core.models import LLMCall


def _config(alias: str, primary: dict[str, Any], fallbacks: list[dict[str, Any]] | None = None):
    return {
        "defaults": {"timeout": 5, "max_retries": 0},
        "aliases": {alias: {"primary": primary, "fallbacks": fallbacks or []}},
    }


def _mock(model: str, response: str) -> dict[str, Any]:
    return {"model": f"openai/{model}", "mock_response": response, "api_key": "mock"}


async def test_un_appel_une_ligne_llm_calls(
    two_orgs: tuple[uuid.UUID, uuid.UUID],
    admin_sessions: async_sessionmaker[AsyncSession],
) -> None:
    """Critère 1 : 1 appel -> 1 ligne llm_calls complète, prompt_version correcte."""
    org_a, _ = two_orgs
    gw = LLMGateway(config=_config("hr.extract", _mock("mock-light", "bonjour")))
    ctx = CallContext(org_id=org_a, agent="hr_extract", prompt_version=3)

    result = await gw.complete("hr.extract", [{"role": "user", "content": "salut"}], ctx=ctx)
    await gw.flush_logs()

    assert result.content == "bonjour"
    async with admin_sessions() as s:
        rows = (
            (await s.execute(select(LLMCall).where(LLMCall.trace_id == ctx.trace_id)))
            .scalars()
            .all()
        )
    assert len(rows) == 1
    row = rows[0]
    assert row.organization_id == org_a
    assert row.agent == "hr_extract"
    assert row.alias == "hr.extract"
    assert row.model_used == "mock-light"
    assert row.prompt_version == 3
    assert row.input_tokens > 0 and row.output_tokens > 0
    assert row.latency_ms >= 0
    assert row.status == "ok"
    assert row.error is None
    assert row.created_at is not None


async def test_primaire_en_echec_repli_utilise(
    two_orgs: tuple[uuid.UUID, uuid.UUID],
    admin_sessions: async_sessionmaker[AsyncSession],
) -> None:
    """Critère 2 : primaire en échec -> repli servi, model_used le reflète."""
    org_a, _ = two_orgs
    gw = LLMGateway(
        config=_config(
            "sales.route",
            _mock("mock-primary", "litellm.RateLimitError"),
            fallbacks=[_mock("mock-fallback", "réponse du repli")],
        )
    )
    ctx = CallContext(org_id=org_a, agent="sales_route")

    result = await gw.complete("sales.route", [{"role": "user", "content": "hi"}], ctx=ctx)
    await gw.flush_logs()

    assert result.content == "réponse du repli"
    assert result.model_used == "mock-fallback"
    async with admin_sessions() as s:
        row = (
            (await s.execute(select(LLMCall).where(LLMCall.trace_id == ctx.trace_id)))
            .scalars()
            .one()
        )
    assert row.model_used == "mock-fallback"
    assert row.status == "ok"


class _Verdict(BaseModel):
    score: int
    verdict: str


class _FakeRouter:
    """Réponses scriptées, fabriquées par litellm (mock_response) — pas de réseau."""

    def __init__(self, contents: list[str]) -> None:
        self._contents = list(contents)
        self.calls: list[list[dict[str, Any]]] = []

    async def acompletion(self, model: str, messages: list[dict[str, Any]], **_: Any) -> Any:
        self.calls.append(messages)
        return litellm.completion(
            model="openai/mock-json",
            messages=messages,
            mock_response=self._contents.pop(0),
            api_key="mock",
        )


async def test_json_invalide_puis_nouvelle_tentative_reussie(
    two_orgs: tuple[uuid.UUID, uuid.UUID],
    admin_sessions: async_sessionmaker[AsyncSession],
) -> None:
    """Critère 3a : 1er JSON invalide -> retentative avec l'erreur -> succès.
    Chaque tentative est un appel LLM journalisé (2 lignes, même trace_id)."""
    org_a, _ = two_orgs
    gw = LLMGateway(config=_config("hr.score", _mock("unused", "unused")))
    fake = _FakeRouter(["pas du tout du json", '{"score": 7, "verdict": "solide"}'])
    gw._router = fake  # fournisseur scripté

    ctx = CallContext(org_id=org_a, agent="hr_score", prompt_version=1)
    result = await gw.complete(
        "hr.score",
        [{"role": "user", "content": "note ce CV"}],
        ctx=ctx,
        response_model=_Verdict,
    )
    await gw.flush_logs()

    assert isinstance(result.parsed, _Verdict)
    assert result.parsed.score == 7
    # La consigne de schéma est présente, et la 2e tentative renvoie l'erreur au modèle.
    assert "schéma" in fake.calls[0][-1]["content"]
    assert "JSON" in fake.calls[1][-1]["content"]
    async with admin_sessions() as s:
        rows = (
            (await s.execute(select(LLMCall).where(LLMCall.trace_id == ctx.trace_id)))
            .scalars()
            .all()
        )
    assert len(rows) == 2  # chaque appel LLM journalisé


async def test_json_toujours_invalide_structured_output_error(
    two_orgs: tuple[uuid.UUID, uuid.UUID],
) -> None:
    """Critère 3b : JSON invalide deux fois -> StructuredOutputError."""
    org_a, _ = two_orgs
    gw = LLMGateway(config=_config("hr.score", _mock("unused", "unused")))
    gw._router = _FakeRouter(["toujours pas du json", '{"score": "sept"}'])

    with pytest.raises(StructuredOutputError):
        await gw.complete(
            "hr.score",
            [{"role": "user", "content": "note"}],
            ctx=CallContext(org_id=org_a, agent="hr_score"),
            response_model=_Verdict,
        )
    await gw.flush_logs()


async def test_alias_inconnu_refuse(two_orgs: tuple[uuid.UUID, uuid.UUID]) -> None:
    gw = LLMGateway(config=_config("hr.extract", _mock("m", "x")))
    with pytest.raises(UnknownAliasError):
        await gw.complete(
            "gpt-4o",  # un nom de modèle n'est PAS un alias (ADR-011)
            [{"role": "user", "content": "x"}],
            ctx=CallContext(org_id=two_orgs[0], agent="test"),
        )


def test_config_reelle_charge_les_quatre_alias() -> None:
    """config/llm.yaml du dépôt : les 4 alias de l'ADR-011 sont définis."""
    gw = LLMGateway()
    assert {"sales.route", "sales.synthesize", "hr.extract", "hr.score"} <= gw._aliases
