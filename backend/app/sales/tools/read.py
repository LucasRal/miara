"""Catalogue d'outils de LECTURE Salesforce, typés et scopés à l'org (ADR-008).

Chaque outil : `Tool(is_write=False)`, `args_schema` Pydantic, docstring
orientée modèle (quand l'utiliser), résultat en modèles compacts (pas de JSON
brut Salesforce), client obtenu par `get_crm(ctx)` (l'org vient du contexte,
jamais des arguments produits par le LLM). Aucun SOQL n'est exposé au modèle :
les requêtes sont construites ici, et l'entrée utilisateur est échappée.

Le composite `get_account_context` ramène tout le contexte d'un compte en un
seul aller-retour (requêtes en parallèle) — brique de la récupération
contextuelle structurée du mémoire (chap. 5 et 8).
"""

import asyncio
from datetime import date, timedelta
from typing import Any

from pydantic import BaseModel, Field, model_validator

from app.config import settings
from app.core.agents.context import RequestContext
from app.core.agents.tool import Tool
from app.sales.context_builder import build
from app.sales.crm import CRMPort, get_crm
from app.sales.tools.cache import cached_json
from app.sales.tools.schemas import (
    AccountContext,
    AccountRef,
    ActivityInfo,
    CaseInfo,
    ContactRef,
    OpportunityInfo,
)

# NE PAS renvoyer plus de 50 enregistrements par outil ; les recherches
# floues sont volontairement plus courtes (5) pour rester lisibles.
MAX_ROWS = 50
MAX_MATCHES = 5

# Projections réutilisées par les résolutions par nom.
_ACCOUNT_FIELDS = "Id, Name, Industry, Phone, Website"
_OPPORTUNITY_FIELDS = "Id, Name, StageName, Amount, CloseDate, AccountId"


def _esc(value: str) -> str:
    """Échappe une valeur pour l'interpoler sans risque dans un littéral SOQL."""
    return value.replace("\\", "\\\\").replace("'", "\\'")


# --- args ----------------------------------------------------------------


class FindContactArgs(BaseModel):
    name: str = Field(description="Nom (ou fragment) du contact à rechercher")
    account_name: str | None = Field(
        default=None, description="Nom du compte pour lever une ambiguïté (optionnel)"
    )


class FindAccountArgs(BaseModel):
    name: str = Field(description="Nom (ou fragment) du compte à rechercher")


class GetOpportunityArgs(BaseModel):
    opportunity_id: str | None = Field(
        default=None, description="Id Salesforce de l'opportunité, si connu"
    )
    opportunity_name: str | None = Field(
        default=None,
        description="Nom (ou fragment) de l'opportunité, si l'id n'est pas connu",
    )

    @model_validator(mode="after")
    def _au_moins_un_identifiant(self) -> "GetOpportunityArgs":
        if not self.opportunity_id and not self.opportunity_name:
            raise ValueError("Fournir opportunity_id ou opportunity_name.")
        return self


class SearchActivitiesArgs(BaseModel):
    record_id: str = Field(description="Id du compte ou de l'opportunité concerné")
    days: int = Field(default=30, ge=1, le=365, description="Fenêtre en jours (défaut 30)")


class GetAccountContextArgs(BaseModel):
    account_id: str | None = Field(default=None, description="Id Salesforce du compte, si connu")
    account_name: str | None = Field(
        default=None,
        description=(
            "Nom (ou fragment) du compte, si l'id n'est pas connu : l'outil le "
            "résout lui-même. Inutile d'appeler find_account avant."
        ),
    )
    window_days: int = Field(
        default=90, ge=1, le=365, description="Fenêtre des activités récentes (jours)"
    )

    @model_validator(mode="after")
    def _au_moins_un_identifiant(self) -> "GetAccountContextArgs":
        if not self.account_id and not self.account_name:
            raise ValueError("Fournir account_id ou account_name.")
        return self


# --- handlers ------------------------------------------------------------


async def _find_contact(args: BaseModel, ctx: RequestContext) -> list[dict[str, Any]]:
    assert isinstance(args, FindContactArgs)

    async def produce() -> list[dict[str, Any]]:
        crm = await get_crm(ctx)
        try:
            conditions = [f"Name LIKE '%{_esc(args.name)}%'"]
            if args.account_name:
                accounts = await crm.query(
                    f"SELECT Id FROM Account WHERE Name LIKE '%{_esc(args.account_name)}%' LIMIT 1"
                )
                if not accounts:
                    return []
                conditions.append(f"AccountId = '{accounts[0]['Id']}'")
            rows = await crm.query(
                "SELECT Id, Name, Email, Phone, Title, AccountId FROM Contact "
                f"WHERE {' AND '.join(conditions)} LIMIT {MAX_MATCHES}"
            )
        finally:
            await crm.aclose()
        return [ContactRef.from_row(r).model_dump(mode="json") for r in rows[:MAX_MATCHES]]

    return await cached_json(ctx.org_id, "find_contact", args, produce)


async def _find_account(args: BaseModel, ctx: RequestContext) -> list[dict[str, Any]]:
    assert isinstance(args, FindAccountArgs)

    async def produce() -> list[dict[str, Any]]:
        crm = await get_crm(ctx)
        try:
            rows = await crm.query(
                "SELECT Id, Name, Industry, Phone, Website FROM Account "
                f"WHERE Name LIKE '%{_esc(args.name)}%' LIMIT {MAX_MATCHES}"
            )
        finally:
            await crm.aclose()
        return [AccountRef.from_row(r).model_dump(mode="json") for r in rows[:MAX_MATCHES]]

    return await cached_json(ctx.org_id, "find_account", args, produce)


async def _get_opportunity(args: BaseModel, ctx: RequestContext) -> dict[str, Any]:
    assert isinstance(args, GetOpportunityArgs)

    async def produce() -> dict[str, Any]:
        crm = await get_crm(ctx)
        try:
            if args.opportunity_id:
                row = await crm.get("Opportunity", args.opportunity_id)
                return OpportunityInfo.from_row(row).model_dump(mode="json")
            # Résolution par nom : évite un aller-retour LLM par find_account.
            name = args.opportunity_name or ""
            rows = await crm.query(
                f"SELECT {_OPPORTUNITY_FIELDS} FROM Opportunity "
                f"WHERE Name LIKE '%{_esc(name)}%' LIMIT {MAX_MATCHES}"
            )
        finally:
            await crm.aclose()
        if not rows:
            return {"error": f"Aucune opportunité ne correspond à « {name} »."}
        found = [OpportunityInfo.from_row(r).model_dump(mode="json") for r in rows]
        if len(found) > 1:
            # Homonymes : on rend les candidates complètes, le modèle tranche
            # sans nouvel appel d'outil.
            return {
                "error": f"Plusieurs opportunités correspondent à « {name} ».",
                "candidates": found,
            }
        return found[0]

    return await cached_json(ctx.org_id, "get_opportunity", args, produce)


async def _activities_since(
    crm: CRMPort, where_id_field: str, record_id: str, days: int
) -> list[ActivityInfo]:
    cutoff = (date.today() - timedelta(days=days)).isoformat()
    base = f"WHERE {where_id_field} = '{_esc(record_id)}' AND ActivityDate >= {cutoff}"
    tasks, events = await asyncio.gather(
        crm.query(
            f"SELECT Id, Subject, ActivityDate, Status FROM Task {base} "
            f"ORDER BY ActivityDate DESC LIMIT {MAX_ROWS}"
        ),
        crm.query(
            f"SELECT Id, Subject, ActivityDate FROM Event {base} "
            f"ORDER BY ActivityDate DESC LIMIT {MAX_ROWS}"
        ),
    )
    activities = [ActivityInfo.from_row(t, "Task") for t in tasks]
    activities += [ActivityInfo.from_row(e, "Event") for e in events]
    activities.sort(key=lambda a: a.date or "", reverse=True)
    return activities[:MAX_ROWS]


async def _search_activities(args: BaseModel, ctx: RequestContext) -> list[dict[str, Any]]:
    assert isinstance(args, SearchActivitiesArgs)

    async def produce() -> list[dict[str, Any]]:
        crm = await get_crm(ctx)
        try:
            activities = await _activities_since(crm, "WhatId", args.record_id, args.days)
        finally:
            await crm.aclose()
        return [a.model_dump(mode="json") for a in activities]

    return await cached_json(ctx.org_id, "search_activities", args, produce)


async def _resolve_account(
    crm: CRMPort, args: GetAccountContextArgs
) -> tuple[tuple[dict[str, Any] | None, str] | None, dict[str, Any] | None]:
    """((fiche du compte si déjà lue, id), None) ou (None, erreur pour le modèle).

    Résoudre le nom ICI évite un aller-retour LLM complet (find_account puis
    get_account_context) : c'est un appel d'outil de moins par briefing.
    """
    if args.account_id:
        return (None, args.account_id), None
    name = args.account_name or ""
    rows = await crm.query(
        f"SELECT {_ACCOUNT_FIELDS} FROM Account WHERE Name LIKE '%{_esc(name)}%' LIMIT 2"
    )
    if not rows:
        return None, {"error": f"Aucun compte ne correspond à « {name} »."}
    if len(rows) > 1:
        return None, {
            "error": f"Plusieurs comptes correspondent à « {name} » : précisez lequel.",
            "candidates": [AccountRef.from_row(r).model_dump(mode="json") for r in rows],
        }
    return (rows[0], rows[0]["Id"]), None


async def fetch_account_context(args: GetAccountContextArgs, ctx: RequestContext) -> dict[str, Any]:
    """Contexte complet d'un compte, STRUCTURÉ (schéma `AccountContext`).

    Sortie destinée au `ContextBuilder` (et aux mesures du mémoire), pas au
    modèle : l'outil, lui, renvoie le rendu compact sous budget.
    """

    async def produce() -> dict[str, Any]:
        crm = await get_crm(ctx)
        try:
            resolved, error = await _resolve_account(crm, args)
            if error is not None:
                return error
            assert resolved is not None
            account_row, account_id = resolved
            aid = _esc(account_id)

            async def account_fiche() -> dict[str, Any]:
                # Déjà en main si le compte a été résolu par son nom.
                return account_row if account_row is not None else await crm.get("Account", aid)

            # Un seul aller-retour : toutes les requêtes en parallèle.
            account, contacts, opps, cases, activities = await asyncio.gather(
                account_fiche(),
                crm.query(
                    "SELECT Id, Name, Email, Phone, Title, AccountId FROM Contact "
                    f"WHERE AccountId = '{aid}' LIMIT {MAX_ROWS}"
                ),
                crm.query(
                    "SELECT Id, Name, StageName, Amount, CloseDate, AccountId FROM Opportunity "
                    f"WHERE AccountId = '{aid}' AND IsClosed = false "
                    f"ORDER BY CloseDate ASC LIMIT {MAX_ROWS}"
                ),
                crm.query(
                    "SELECT Id, CaseNumber, Subject, Status, Priority FROM Case "
                    f"WHERE AccountId = '{aid}' AND IsClosed = false LIMIT {MAX_ROWS}"
                ),
                _activities_since(crm, "WhatId", account_id, args.window_days),
            )
        finally:
            await crm.aclose()
        return AccountContext(
            account=AccountRef.from_row(account),
            contacts=[ContactRef.from_row(r) for r in contacts],
            open_opportunities=[OpportunityInfo.from_row(r) for r in opps],
            recent_activities=activities,
            open_cases=[CaseInfo.from_row(r) for r in cases],
        ).model_dump(mode="json")

    return await cached_json(ctx.org_id, "get_account_context", args, produce)


async def _get_account_context(args: BaseModel, ctx: RequestContext) -> dict[str, Any]:
    """Outil composite : les données passent par le `ContextBuilder` AVANT
    d'être rendues au modèle (budget fixé par la configuration, jamais par le
    modèle). Le texte porte les ids pour que l'agent cite ses sources."""
    assert isinstance(args, GetAccountContextArgs)
    structured = await fetch_account_context(args, ctx)
    if "error" in structured:  # compte introuvable ou ambigu : le modèle tranche
        return structured
    built = build(structured, budget_tokens=settings.SALES_CONTEXT_BUDGET_TOKENS)
    return {
        "context": built.text,
        "tokens_used": built.tokens_used,
        "items_dropped": built.items_dropped,
    }


# --- catalogue -----------------------------------------------------------

find_contact = Tool(
    name="find_contact",
    description=(
        "Recherche des contacts par nom (correspondance partielle), max 5. "
        "Préciser account_name pour lever une ambiguïté entre homonymes. "
        "Retourne id, nom, email, téléphone, fonction et l'id du compte."
    ),
    args_schema=FindContactArgs,
    is_write=False,
    handler=_find_contact,
)

find_account = Tool(
    name="find_account",
    description=(
        "Recherche des comptes (entreprises) par nom, correspondance partielle, "
        "max 5. Retourne id, nom, secteur, téléphone, site web. Utiliser d'abord "
        "cet outil pour obtenir un account_id."
    ),
    args_schema=FindAccountArgs,
    is_write=False,
    handler=_find_account,
)

get_opportunity = Tool(
    name="get_opportunity",
    description=(
        "Détail d'une opportunité par son id OU par son nom : étape (StageName), "
        "montant, date de clôture prévue, compte rattaché. En cas d'homonymes, "
        "renvoie les candidates avec leurs ids."
    ),
    args_schema=GetOpportunityArgs,
    is_write=False,
    handler=_get_opportunity,
)

search_activities = Tool(
    name="search_activities",
    description=(
        "Activités (tâches et événements) liées à un compte ou une opportunité "
        "sur les N derniers jours (défaut 30), triées de la plus récente à la "
        "plus ancienne."
    ),
    args_schema=SearchActivitiesArgs,
    is_write=False,
    handler=_search_activities,
)

get_account_context = Tool(
    name="get_account_context",
    description=(
        "Vue complète d'un compte en un seul appel, rendue en texte compact : "
        "fiche du compte, opportunités ouvertes, activités récentes, contacts "
        "et cas ouverts, avec les ids d'enregistrements. Accepte account_id ou "
        "directement account_name (résolu par l'outil). À privilégier pour "
        "préparer un échange avec un client plutôt que d'enchaîner les outils "
        "atomiques."
    ),
    args_schema=GetAccountContextArgs,
    is_write=False,
    handler=_get_account_context,
)

READ_TOOLS: list[Tool] = [
    find_account,
    find_contact,
    get_opportunity,
    search_activities,
    get_account_context,
]
