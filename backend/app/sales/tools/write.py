"""Outils d'ÉCRITURE Salesforce, sûrs par construction (ADR-009).

Le « flux inverse » : l'agent écrit dans le CRM à la place du commercial. Trois
garde-fous :
- `is_write=True` → la boucle exige une confirmation humaine AVANT exécution ;
- idempotence par `(org, trace_id, call_id)` en Redis (24 h) : une confirmation
  rejouée ne crée pas de doublon ;
- chaque tentative est tracée dans `crm_writes` (piste d'audit).

Chaque outil expose un `preview(args, ctx)` en français pour l'écran de
confirmation. Les outils de CRÉATION s'en servent pour montrer les homonymes
déjà présents dans le CRM : on ne bloque jamais une création, on donne à
l'humain de quoi ne pas fabriquer un doublon sans le savoir.
Les erreurs Salesforce (champ requis, permission) sont renvoyées AU MODÈLE comme
résultat d'outil, jamais levées en exception. NE PAS : supprimer, écrire sans
confirmation, toucher Amount/CloseDate (hors périmètre).
"""

import json
import uuid
from collections.abc import Awaitable, Callable
from datetime import date
from typing import Any

import redis.asyncio as aioredis
import structlog
from pydantic import BaseModel, Field

from app.config import settings
from app.core.agents.context import RequestContext
from app.core.agents.tool import Tool
from app.core.tenant import tenant_session
from app.sales.crm import CRMError, CRMPort, get_crm
from app.sales.models import CrmWrite

logger = structlog.get_logger(__name__)

IDEM_TTL_SECONDS = 24 * 3600
STAGES_TTL_SECONDS = 3600
_IDEM_PREFIX = "crm:write:"
_STAGES_PREFIX = "sales:oppstages:"

_redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)


def _fr_date(iso: str) -> str:
    """'2026-09-08' -> '08/09/2026' (repli sur la valeur brute si non ISO)."""
    try:
        return date.fromisoformat(iso).strftime("%d/%m/%Y")
    except ValueError:
        return iso


# --- args ----------------------------------------------------------------


class CreateTaskArgs(BaseModel):
    subject: str = Field(description="Intitulé de la tâche")
    due_date: str = Field(description="Échéance au format AAAA-MM-JJ")
    related_record_id: str = Field(description="Id du compte ou de l'opportunité liée")
    contact_id: str | None = Field(default=None, description="Id du contact concerné (optionnel)")
    priority: str = Field(default="Normal", description="Priorité (Low, Normal, High)")


class LogCallNoteArgs(BaseModel):
    record_id: str = Field(description="Id du compte, contact ou opportunité concerné")
    summary: str = Field(description="Résumé de l'appel (objet de la tâche)")
    outcome: str = Field(description="Issue de l'appel (corps de la note)")


class CreateContactArgs(BaseModel):
    last_name: str = Field(description="Nom de famille (obligatoire côté Salesforce)")
    first_name: str | None = Field(default=None, description="Prénom (optionnel)")
    account_id: str | None = Field(
        default=None, description="Id du compte auquel rattacher le contact (optionnel)"
    )
    title: str | None = Field(default=None, description="Fonction, par exemple « CEO »")
    email: str | None = Field(default=None, description="Adresse e-mail (optionnel)")
    phone: str | None = Field(default=None, description="Téléphone (optionnel)")


class CreateAccountArgs(BaseModel):
    name: str = Field(description="Raison sociale du compte")
    industry: str | None = Field(default=None, description="Secteur (optionnel)")
    website: str | None = Field(default=None, description="Site web (optionnel)")
    phone: str | None = Field(default=None, description="Téléphone (optionnel)")


class CreateOpportunityArgs(BaseModel):
    name: str = Field(description="Nom de l'opportunité")
    account_id: str = Field(description="Id du compte concerné")
    stage: str = Field(description="Étape de départ (doit être une étape active de l'org)")
    close_date: str = Field(description="Date de clôture prévue, au format AAAA-MM-JJ")
    amount: float | None = Field(default=None, description="Montant prévu (optionnel)")


class UpdateOpportunityStageArgs(BaseModel):
    opportunity_id: str = Field(description="Id de l'opportunité")
    stage: str = Field(description="Nouvelle étape (doit être une étape active de l'org)")
    next_step: str | None = Field(default=None, description="Prochaine action (optionnel)")


# --- idempotence & audit -------------------------------------------------


async def _idempotent(
    ctx: RequestContext, tool: str, producer: Callable[[], Awaitable[dict[str, Any]]]
) -> dict[str, Any]:
    """Exécute `producer` une seule fois par (org, trace_id, call_id). Les
    rejeux renvoient le résultat mémorisé. Seuls les succès sont mémorisés :
    une erreur transitoire reste réessayable."""
    call_id = ctx.call_id or uuid.uuid4().hex
    key = f"{_IDEM_PREFIX}{ctx.org_id}:{ctx.trace_id}:{call_id}"
    cached = await _redis.get(key)
    if cached is not None:
        return dict(json.loads(cached))
    result = await producer()
    if "error" not in result:
        await _redis.set(key, json.dumps(result, default=str), ex=IDEM_TTL_SECONDS)
    return result


async def _audit(
    ctx: RequestContext,
    tool: str,
    args: BaseModel,
    sf_record_id: str | None,
    status: str,
    error: str | None,
) -> None:
    async with tenant_session(ctx.org_id, ctx.user_id) as session:
        session.add(
            CrmWrite(
                organization_id=ctx.org_id,
                trace_id=ctx.trace_id,
                tool=tool,
                args_json=args.model_dump(mode="json"),
                sf_record_id=sf_record_id,
                status=status,
                confirmed_by=ctx.user_id,
                error=error,
            )
        )


async def _write(
    ctx: RequestContext,
    tool: str,
    args: BaseModel,
    do_write: Callable[[CRMPort], Awaitable[str]],
) -> dict[str, Any]:
    """Ossature commune : idempotence → écriture CRM → audit. `do_write`
    renvoie l'id Salesforce créé/modifié."""

    async def producer() -> dict[str, Any]:
        crm = await get_crm(ctx)
        try:
            record_id = await do_write(crm)
        except CRMError as exc:
            await _audit(ctx, tool, args, None, "error", str(exc))
            logger.warning("crm_write_failed", tool=tool, trace_id=str(ctx.trace_id))
            return {"error": f"Salesforce a refusé l'écriture : {exc}"}
        finally:
            await crm.aclose()
        await _audit(ctx, tool, args, record_id, "created", None)
        logger.info("crm_write", tool=tool, sf_record_id=record_id, trace_id=str(ctx.trace_id))
        return {"status": "created", "sf_record_id": record_id}

    return await _idempotent(ctx, tool, producer)


async def _active_stages(ctx: RequestContext, crm: CRMPort) -> list[str]:
    """Étapes d'opportunité actives de l'org, cachées 1 h."""
    key = f"{_STAGES_PREFIX}{ctx.org_id}"
    cached = await _redis.get(key)
    if cached is not None:
        return list(json.loads(cached))
    rows = await crm.query("SELECT MasterLabel FROM OpportunityStage WHERE IsActive = true")
    stages = [r["MasterLabel"] for r in rows if r.get("MasterLabel")]
    await _redis.set(key, json.dumps(stages), ex=STAGES_TTL_SECONDS)
    return stages


# --- homonymes -----------------------------------------------------------

MAX_HOMONYMES = 5


def _echappe(valeur: str) -> str:
    """Neutralise les quotes d'une valeur injectée dans une clause SOQL."""
    return valeur.replace("\\", "\\\\").replace("'", "\\'")


class _HomonymesIndisponibles(Exception):
    """Le CRM n'a pas pu répondre à la recherche d'homonymes."""


async def _interroger(ctx: RequestContext, soql: str) -> list[dict[str, Any]]:
    """Lecture tolérante à la panne : un aperçu ne doit jamais empêcher une
    confirmation. Si le CRM refuse la requête, on le DIT dans l'aperçu plutôt
    que de laisser croire qu'aucun homonyme n'existe."""
    crm = await get_crm(ctx)
    try:
        return await crm.query(soql)
    except CRMError as exc:
        raise _HomonymesIndisponibles(str(exc)) from exc
    finally:
        await crm.aclose()


async def _lignes_homonymes(
    ctx: RequestContext, soql: str, rendu: Callable[[dict[str, Any]], str]
) -> list[str]:
    try:
        lignes = await _interroger(ctx, soql)
    except _HomonymesIndisponibles as exc:
        return [f"Recherche de doublons impossible ({exc}) : vérifiez vous-même avant de créer."]
    if not lignes:
        return ["Aucun enregistrement proche trouvé."]
    trouves = [rendu(ligne) for ligne in lignes[:MAX_HOMONYMES]]
    reste = len(lignes) - len(trouves)
    if reste > 0:
        trouves.append(f"… et {reste} autre(s).")
    return trouves


def _bloc(titre: str, lignes: list[str]) -> str:
    return "\n".join([titre, *[f"  - {ligne}" for ligne in lignes]])


# --- handlers ------------------------------------------------------------


async def _create_task(args: BaseModel, ctx: RequestContext) -> dict[str, Any]:
    assert isinstance(args, CreateTaskArgs)

    async def do_write(crm: CRMPort) -> str:
        payload: dict[str, Any] = {
            "Subject": args.subject,
            "ActivityDate": args.due_date,
            "WhatId": args.related_record_id,
            "Priority": args.priority,
            "Status": "Not Started",
        }
        if args.contact_id:
            payload["WhoId"] = args.contact_id
        return await crm.create("Task", payload)

    return await _write(ctx, "create_task", args, do_write)


async def _log_call_note(args: BaseModel, ctx: RequestContext) -> dict[str, Any]:
    assert isinstance(args, LogCallNoteArgs)

    async def do_write(crm: CRMPort) -> str:
        return await crm.create(
            "Task",
            {
                "Subject": args.summary,
                "Description": args.outcome,
                "TaskSubtype": "Call",
                "Status": "Completed",
                "ActivityDate": date.today().isoformat(),
                "WhatId": args.record_id,
            },
        )

    return await _write(ctx, "log_call_note", args, do_write)


async def _create_contact(args: BaseModel, ctx: RequestContext) -> dict[str, Any]:
    assert isinstance(args, CreateContactArgs)

    async def do_write(crm: CRMPort) -> str:
        payload: dict[str, Any] = {"LastName": args.last_name}
        for champ, valeur in (
            ("FirstName", args.first_name),
            ("AccountId", args.account_id),
            ("Title", args.title),
            ("Email", args.email),
            ("Phone", args.phone),
        ):
            if valeur:
                payload[champ] = valeur
        return await crm.create("Contact", payload)

    return await _write(ctx, "create_contact", args, do_write)


async def _create_account(args: BaseModel, ctx: RequestContext) -> dict[str, Any]:
    assert isinstance(args, CreateAccountArgs)

    async def do_write(crm: CRMPort) -> str:
        payload: dict[str, Any] = {"Name": args.name}
        for champ, valeur in (
            ("Industry", args.industry),
            ("Website", args.website),
            ("Phone", args.phone),
        ):
            if valeur:
                payload[champ] = valeur
        return await crm.create("Account", payload)

    return await _write(ctx, "create_account", args, do_write)


async def _create_opportunity(args: BaseModel, ctx: RequestContext) -> dict[str, Any]:
    assert isinstance(args, CreateOpportunityArgs)

    # Validations AVANT toute écriture, comme pour le changement d'étape :
    # une valeur refusée revient au modèle, elle ne crée rien à moitié.
    try:
        date.fromisoformat(args.close_date)
    except ValueError:
        return {
            "error": (f"Date de clôture invalide : {args.close_date!r}. Format attendu AAAA-MM-JJ.")
        }
    crm = await get_crm(ctx)
    try:
        stages = await _active_stages(ctx, crm)
    finally:
        await crm.aclose()
    if args.stage not in stages:
        return {
            "error": (f"Étape invalide : {args.stage!r}. Étapes actives : {', '.join(stages)}.")
        }

    async def do_write(crm: CRMPort) -> str:
        payload: dict[str, Any] = {
            "Name": args.name,
            "AccountId": args.account_id,
            "StageName": args.stage,
            "CloseDate": args.close_date,
        }
        if args.amount is not None:
            payload["Amount"] = args.amount
        return await crm.create("Opportunity", payload)

    return await _write(ctx, "create_opportunity", args, do_write)


async def _update_opportunity_stage(args: BaseModel, ctx: RequestContext) -> dict[str, Any]:
    assert isinstance(args, UpdateOpportunityStageArgs)

    # Validation AVANT toute écriture : l'étape doit être active dans l'org.
    crm = await get_crm(ctx)
    try:
        stages = await _active_stages(ctx, crm)
    finally:
        await crm.aclose()
    if args.stage not in stages:
        return {
            "error": (f"Étape invalide : {args.stage!r}. Étapes actives : {', '.join(stages)}.")
        }

    async def do_write(crm: CRMPort) -> str:
        payload: dict[str, Any] = {"StageName": args.stage}
        if args.next_step:
            payload["NextStep"] = args.next_step
        await crm.update("Opportunity", args.opportunity_id, payload)
        return args.opportunity_id

    return await _write(ctx, "update_opportunity_stage", args, do_write)


# --- previews ------------------------------------------------------------


async def _preview_create_task(args: BaseModel, ctx: RequestContext) -> str:
    assert isinstance(args, CreateTaskArgs)
    return (
        f"Créer une tâche « {args.subject} » le {_fr_date(args.due_date)} "
        f"liée à {args.related_record_id}"
    )


async def _preview_log_call_note(args: BaseModel, ctx: RequestContext) -> str:
    assert isinstance(args, LogCallNoteArgs)
    return (
        f"Journaliser un appel sur {args.record_id} : « {args.summary} » (issue : {args.outcome})"
    )


async def _preview_update_stage(args: BaseModel, ctx: RequestContext) -> str:
    assert isinstance(args, UpdateOpportunityStageArgs)
    return f"Faire passer l'opportunité {args.opportunity_id} à l'étape « {args.stage} »"


async def _preview_create_contact(args: BaseModel, ctx: RequestContext) -> str:
    assert isinstance(args, CreateContactArgs)
    identite = " ".join(filter(None, [args.first_name, args.last_name]))
    compte = f"compte {args.account_id}" if args.account_id else None
    detail = ", ".join(filter(None, [args.title, args.email, args.phone, compte]))
    lignes = await _lignes_homonymes(
        ctx,
        "SELECT Id, Name, Title, Email, AccountId FROM Contact "
        f"WHERE Name LIKE '%{_echappe(args.last_name)}%' LIMIT 20",
        lambda r: " · ".join(
            filter(None, [str(r.get("Name") or "?"), r.get("Title"), r.get("Email"), r.get("Id")])
        ),
    )
    entete = f"Créer le contact « {identite} »" + (f" ({detail})" if detail else "")
    return _bloc(entete + "\n\nContacts déjà présents portant ce nom :", lignes)


async def _preview_create_account(args: BaseModel, ctx: RequestContext) -> str:
    assert isinstance(args, CreateAccountArgs)
    detail = ", ".join(filter(None, [args.industry, args.website, args.phone]))
    lignes = await _lignes_homonymes(
        ctx,
        "SELECT Id, Name, Industry FROM Account "
        f"WHERE Name LIKE '%{_echappe(args.name)}%' LIMIT 20",
        lambda r: " · ".join(
            filter(None, [str(r.get("Name") or "?"), r.get("Industry"), r.get("Id")])
        ),
    )
    entete = f"Créer le compte « {args.name} »" + (f" ({detail})" if detail else "")
    return _bloc(entete + "\n\nComptes déjà présents portant ce nom :", lignes)


async def _preview_create_opportunity(args: BaseModel, ctx: RequestContext) -> str:
    assert isinstance(args, CreateOpportunityArgs)
    # Espace fine comme séparateur de milliers. Le remplacement porte sur le
    # seul nombre : appliqué à la phrase entière, il effaçait aussi la virgule
    # qui sépare « clôture au ... » de « montant ... ».
    montant = ""
    if args.amount is not None:
        montant = ", montant " + f"{args.amount:,.0f}".replace(",", " ")
    lignes = await _lignes_homonymes(
        ctx,
        "SELECT Id, Name, StageName, CloseDate FROM Opportunity "
        f"WHERE AccountId = '{_echappe(args.account_id)}' LIMIT 20",
        lambda r: " · ".join(
            filter(
                None,
                [str(r.get("Name") or "?"), r.get("StageName"), r.get("CloseDate"), r.get("Id")],
            )
        ),
    )
    entete = (
        f"Créer l'opportunité « {args.name} » sur le compte {args.account_id}, "
        f"étape « {args.stage} », clôture au {_fr_date(args.close_date)}{montant}"
    )
    return _bloc(entete + "\n\nOpportunités déjà ouvertes sur ce compte :", lignes)


# --- catalogue -----------------------------------------------------------

create_task = Tool(
    name="create_task",
    description=(
        "Crée une tâche de suivi liée à un compte ou une opportunité. "
        "Nécessite une confirmation humaine avant écriture."
    ),
    args_schema=CreateTaskArgs,
    is_write=True,
    handler=_create_task,
    preview=_preview_create_task,
)

log_call_note = Tool(
    name="log_call_note",
    description=(
        "Journalise un appel téléphonique (tâche de type Call, marquée terminée "
        "à la date du jour). Nécessite une confirmation humaine."
    ),
    args_schema=LogCallNoteArgs,
    is_write=True,
    handler=_log_call_note,
    preview=_preview_log_call_note,
)

update_opportunity_stage = Tool(
    name="update_opportunity_stage",
    description=(
        "Fait passer une opportunité à une nouvelle étape (parmi les étapes "
        "actives de l'organisation). N'affecte ni le montant ni la date de "
        "clôture. Nécessite une confirmation humaine."
    ),
    args_schema=UpdateOpportunityStageArgs,
    is_write=True,
    handler=_update_opportunity_stage,
    preview=_preview_update_stage,
)

create_contact = Tool(
    name="create_contact",
    description=(
        "Crée un contact dans Salesforce. L'écran de confirmation montre les "
        "contacts déjà présents portant le même nom, pour éviter un doublon. "
        "Nécessite une confirmation humaine avant écriture."
    ),
    args_schema=CreateContactArgs,
    is_write=True,
    handler=_create_contact,
    preview=_preview_create_contact,
)

create_account = Tool(
    name="create_account",
    description=(
        "Crée un compte (entreprise) dans Salesforce. L'écran de confirmation "
        "montre les comptes déjà présents portant un nom proche. Nécessite une "
        "confirmation humaine avant écriture."
    ),
    args_schema=CreateAccountArgs,
    is_write=True,
    handler=_create_account,
    preview=_preview_create_account,
)

create_opportunity = Tool(
    name="create_opportunity",
    description=(
        "Crée une opportunité sur un compte, avec son étape de départ et sa "
        "date de clôture prévue. L'écran de confirmation montre les "
        "opportunités déjà ouvertes sur ce compte. Nécessite une confirmation "
        "humaine avant écriture."
    ),
    args_schema=CreateOpportunityArgs,
    is_write=True,
    handler=_create_opportunity,
    preview=_preview_create_opportunity,
)

WRITE_TOOLS: list[Tool] = [
    create_task,
    log_call_note,
    update_opportunity_stage,
    create_contact,
    create_account,
    create_opportunity,
]
