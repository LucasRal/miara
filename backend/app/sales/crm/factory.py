"""Fabrique `get_crm(ctx) -> CRMPort` — SEUL point d'accès au CRM d'une org.

Charge l'intégration de `ctx.org_id` (sous RLS), déchiffre les credentials et
construit un client NEUF à chaque appel : jamais de client partagé entre
organisations, jamais d'org_id venant d'un argument produit par le LLM —
uniquement du contexte de requête ou de tâche.
"""

import uuid
from typing import Any, Protocol

from sqlalchemy import select

from app.core.crypto import decrypt_credentials, encrypt_credentials
from app.core.models import Integration
from app.core.tenant import tenant_session
from app.sales.crm.fake import FakeCRM
from app.sales.crm.port import CRMAuthError, CRMPort
from app.sales.crm.salesforce import SalesforceClient


class HasOrgId(Protocol):
    """Contexte minimal accepté : requête HTTP (auth.deps.RequestContext) ou
    exécution d'agent (core.agents.RequestContext, dataclass figée)."""

    @property
    def org_id(self) -> uuid.UUID: ...


# Mode démo : un FakeCRM persistant (en mémoire) par organisation.
_fakes: dict[uuid.UUID, FakeCRM] = {}


def register_fake(org_id: uuid.UUID, crm: FakeCRM) -> None:
    """Associe un FakeCRM (peuplé) à une org — mode démo et tests. L'org doit
    aussi avoir une intégration `mode=fake` pour que `get_crm` le renvoie."""
    _fakes[org_id] = crm


def clear_fake(org_id: uuid.UUID) -> None:
    _fakes.pop(org_id, None)


async def get_crm(ctx: HasOrgId) -> CRMPort:
    org_id = ctx.org_id
    async with tenant_session(org_id) as session:
        integration = (
            await session.execute(select(Integration).where(Integration.provider == "salesforce"))
        ).scalar_one_or_none()

    if integration is None:
        raise CRMAuthError("Aucun CRM connecté pour cette organisation")

    credentials = decrypt_credentials(integration.encrypted_credentials)
    if credentials.get("mode") == "fake":  # mode démo, sans Salesforce réel
        return _fakes.setdefault(org_id, FakeCRM())
    if not all(k in credentials for k in ("instance_url", "access_token", "refresh_token")):
        raise CRMAuthError("Credentials d'intégration incomplets — reconnexion requise")

    integration_id = integration.id

    async def persist_refreshed(tokens: dict[str, Any]) -> None:
        """Re-chiffre les credentials après un refresh (le refresh token
        d'origine reste valable si Salesforce n'en renvoie pas de nouveau)."""
        updated = {
            **credentials,
            "access_token": str(tokens["access_token"]),
            "refresh_token": str(tokens.get("refresh_token") or credentials["refresh_token"]),
        }
        async with tenant_session(org_id) as session:
            row = await session.get(Integration, integration_id)
            if row is not None:
                row.encrypted_credentials = encrypt_credentials(updated)

    return SalesforceClient(
        instance_url=credentials["instance_url"],
        access_token=credentials["access_token"],
        refresh_token=credentials["refresh_token"],
        on_refresh=persist_refreshed,
    )
