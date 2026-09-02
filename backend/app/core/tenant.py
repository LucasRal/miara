"""Contexte locataire : pose `app.current_org` avant tout accès métier (ADR-002).

`tenant_session(org_id)` ouvre une transaction et exécute
`set_config('app.current_org', <org>, true)` (équivalent transactionnel de
SET LOCAL) AVANT toute requête. Les politiques RLS filtrent alors chaque table
métier sur cette organisation ; sans ce réglage, aucune ligne n'est visible.

L'org_id vient TOUJOURS du contexte de requête (JWT / membership - carte
auth), jamais d'un argument produit par le LLM. Utilisation FastAPI :

    async def get_tenant_session(org_id: OrgFromAuth) -> AsyncIterator[AsyncSession]:
        async with tenant_session(org_id) as session:
            yield session
"""

import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import async_session


@asynccontextmanager
async def tenant_session(org_id: uuid.UUID) -> AsyncIterator[AsyncSession]:
    async with async_session() as session:
        async with session.begin():
            await session.execute(
                text("SELECT set_config('app.current_org', :org, true)"),
                {"org": str(org_id)},
            )
            yield session
