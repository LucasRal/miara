"""Tests de la carte [SALES] outils d'écriture (confirmation + idempotence).

Écritures contre FakeCRM (mode fake), audit `crm_writes` en base sous RLS,
idempotence via Redis. La confirmation elle-même est portée par le runtime.
"""

import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.agents import AgentDefinition, NeedsConfirmation, RequestContext, run
from app.core.llm import LLMResult
from app.sales.crm.factory import _fakes
from app.sales.models import CrmWrite
from app.sales.tools import (
    WRITE_TOOLS,
    create_task,
    log_call_note,
    update_opportunity_stage,
)
from app.sales.tools.write import (
    CreateTaskArgs,
    LogCallNoteArgs,
    UpdateOpportunityStageArgs,
)


def _ctx(org_id: uuid.UUID, call_id: str | None = None) -> RequestContext:
    return RequestContext(
        org_id=org_id, user_id=uuid.uuid4(), role="sales", trace_id=uuid.uuid4(), call_id=call_id
    )


async def _crm_writes_count(
    admin_sessions: async_sessionmaker[AsyncSession], org_id: uuid.UUID
) -> int:
    async with admin_sessions() as s:
        return (
            await s.execute(
                select(func.count()).select_from(CrmWrite).where(CrmWrite.organization_id == org_id)
            )
        ).scalar_one()


# --- LLM simulé : émet un appel de l'outil d'écriture --------------------


class _WriteGateway:
    def __init__(self, tool_name: str, args: dict[str, Any]) -> None:
        self._tool_name = tool_name
        self._args = args

    async def complete(self, alias: str, messages: Any, *, ctx: Any, **_: Any) -> LLMResult:
        import json

        return LLMResult(
            content=None,
            parsed=None,
            tool_calls=[{"id": "w1", "name": self._tool_name, "arguments": json.dumps(self._args)}],
            model_used="fake",
            input_tokens=1,
            output_tokens=1,
            latency_ms=1,
            cost_usd=None,
            trace_id=uuid.uuid4(),
        )


async def test_appel_non_confirme_n_ecrit_rien(
    seeded_org: tuple[uuid.UUID, dict[str, str]],
    admin_sessions: async_sessionmaker[AsyncSession],
) -> None:
    """Critère 1 : sans confirmation → NeedsConfirmation, aucune écriture."""
    org_id, ids = seeded_org
    agent = AgentDefinition(
        name="sales_write_test",
        model_alias="sales.route",
        prompt_name="echo",
        tools=[create_task],
    )
    gw = _WriteGateway(
        "create_task",
        {
            "subject": "Relance TechStart",
            "due_date": "2026-09-30",
            "related_record_id": ids["techstart"],
        },
    )
    before = len(await _fakes[org_id].query("SELECT Id FROM Task"))
    result = await run(agent, "Crée une tâche de relance.", _ctx(org_id), gateway=gw)

    assert isinstance(result, NeedsConfirmation)
    assert result.tool == "create_task"
    assert result.preview and "Relance TechStart" in result.preview  # rendu pour l'UI
    # Aucun enregistrement CRM créé, aucune ligne d'audit.
    assert len(await _fakes[org_id].query("SELECT Id FROM Task")) == before
    assert await _crm_writes_count(admin_sessions, org_id) == 0


async def test_confirmation_rejouee_trois_fois_un_seul_enregistrement(
    seeded_org: tuple[uuid.UUID, dict[str, str]],
    admin_sessions: async_sessionmaker[AsyncSession],
) -> None:
    """Critère 2 : idempotence par (org, trace_id, call_id)."""
    org_id, ids = seeded_org
    ctx = _ctx(org_id, call_id="w1")
    args = CreateTaskArgs(
        subject="Relance", due_date="2026-09-30", related_record_id=ids["techstart"]
    )

    before = len(await _fakes[org_id].query("SELECT Id FROM Task"))
    first = await create_task.run(args, ctx)
    second = await create_task.run(args, ctx)
    third = await create_task.run(args, ctx)

    assert first["status"] == "created"
    assert second == first and third == first  # rejeux : même résultat mémorisé
    after = len(await _fakes[org_id].query("SELECT Id FROM Task"))
    assert after - before == 1  # un seul enregistrement Salesforce créé
    assert await _crm_writes_count(admin_sessions, org_id) == 1


async def test_stage_invalide_refuse_avant_ecriture(
    seeded_org: tuple[uuid.UUID, dict[str, str]],
    admin_sessions: async_sessionmaker[AsyncSession],
) -> None:
    """Critère 3 : étape hors des étapes actives → refus, rien n'est écrit."""
    org_id, ids = seeded_org
    before = await _fakes[org_id].get("Opportunity", ids["opp_open"])

    result = await update_opportunity_stage.run(
        UpdateOpportunityStageArgs(opportunity_id=ids["opp_open"], stage="Inexistante"),
        _ctx(org_id, call_id="s1"),
    )

    assert "error" in result and "Inexistante" in result["error"]
    after = await _fakes[org_id].get("Opportunity", ids["opp_open"])
    assert after["StageName"] == before["StageName"]  # inchangé
    assert await _crm_writes_count(admin_sessions, org_id) == 0


async def test_update_stage_valide_ecrit(
    seeded_org: tuple[uuid.UUID, dict[str, str]],
    admin_sessions: async_sessionmaker[AsyncSession],
) -> None:
    org_id, ids = seeded_org
    result = await update_opportunity_stage.run(
        UpdateOpportunityStageArgs(
            opportunity_id=ids["opp_open"], stage="Négociation", next_step="Envoyer le devis"
        ),
        _ctx(org_id, call_id="s2"),
    )
    assert result["status"] == "created" and result["sf_record_id"] == ids["opp_open"]
    opp = await _fakes[org_id].get("Opportunity", ids["opp_open"])
    assert opp["StageName"] == "Négociation" and opp["NextStep"] == "Envoyer le devis"
    assert await _crm_writes_count(admin_sessions, org_id) == 1


async def test_log_call_note_cree_une_tache_call(
    seeded_org: tuple[uuid.UUID, dict[str, str]],
) -> None:
    org_id, ids = seeded_org
    result = await log_call_note.run(
        LogCallNoteArgs(record_id=ids["techstart"], summary="Point mensuel", outcome="RAS"),
        _ctx(org_id, call_id="c1"),
    )
    task = await _fakes[org_id].get("Task", result["sf_record_id"])
    assert task["TaskSubtype"] == "Call" and task["Status"] == "Completed"
    assert task["Subject"] == "Point mensuel"


async def test_erreur_salesforce_remontee_au_modele(
    seeded_org: tuple[uuid.UUID, dict[str, str]],
    admin_sessions: async_sessionmaker[AsyncSession],
) -> None:
    """Une erreur CRM devient un résultat d'outil (pas une exception) et est
    tracée en `error` — et n'est PAS mémorisée (réessayable)."""
    org_id, ids = seeded_org
    # opportunity_id inexistant → CRMError 404 sur l'update.
    ctx = _ctx(org_id, call_id="e1")
    result = await update_opportunity_stage.run(
        UpdateOpportunityStageArgs(opportunity_id="006INEXISTANT", stage="Négociation"), ctx
    )
    assert "error" in result
    async with admin_sessions() as s:
        row = (
            await s.execute(select(CrmWrite).where(CrmWrite.organization_id == org_id))
        ).scalar_one()
    assert row.status == "error" and row.sf_record_id is None

    # Rejeu autorisé après erreur : une 2e tentative retente réellement.
    result2 = await update_opportunity_stage.run(
        UpdateOpportunityStageArgs(opportunity_id="006INEXISTANT", stage="Négociation"), ctx
    )
    assert "error" in result2
    count = await _crm_writes_count(admin_sessions, org_id)
    assert count == 2  # deux tentatives tracées (erreur non mémorisée)


async def test_schemas_et_previews_des_outils_ecriture() -> None:
    for tool in WRITE_TOOLS:
        assert tool.is_write
        schema = tool.to_llm_schema()
        assert schema["function"]["name"] == tool.name
        assert tool.preview is not None  # rendu de confirmation obligatoire

    preview = create_task.render_preview(
        CreateTaskArgs(
            subject="Relance TechStart", due_date="2026-09-08", related_record_id="006xx"
        )
    )
    assert preview is not None
    assert "Relance TechStart" in preview and "08/09/2026" in preview
