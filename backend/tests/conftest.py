"""Fixtures partagées : sessions admin (BYPASSRLS), données A/B, clients HTTP."""

import uuid
from collections.abc import AsyncIterator, Callable
from typing import Annotated

import httpx
import pytest
from fastapi import APIRouter, Depends
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.auth.deps import RequestContext, get_context
from app.auth.models import Organization, User
from app.config import settings
from app.core.crypto import encrypt_credentials
from app.core.models import Integration
from app.main import api_prefix, app

# Route DE TEST uniquement : un SELECT ORM sans filtre derrière la chaîne
# JWT -> contexte -> RLS. Prouve que deux orgs voient des données différentes
# (critère 1 de la carte auth) sans inventer d'endpoint produit prématuré.
_test_router = APIRouter()


@_test_router.get("/_test/integrations")
async def _list_visible_integrations(
    ctx: Annotated[RequestContext, Depends(get_context)],
) -> list[str]:
    rows = (await ctx.session.execute(select(Integration))).scalars().all()
    return [row.instance_url or "" for row in rows]


app.include_router(_test_router, prefix=api_prefix)


@pytest.fixture
async def make_client() -> AsyncIterator[Callable[[], httpx.AsyncClient]]:
    """Fabrique de clients HTTP ASGI — un client (donc un jar de cookies) par acteur."""
    clients: list[httpx.AsyncClient] = []

    def _make() -> httpx.AsyncClient:
        client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")
        clients.append(client)
        return client

    yield _make
    for client in clients:
        await client.aclose()


@pytest.fixture
async def auth_cleanup(
    admin_sessions: async_sessionmaker[AsyncSession],
) -> AsyncIterator[dict[str, list]]:
    """Registre {emails, org_ids} ; supprime en fin de test (cascade memberships)."""
    registry: dict[str, list] = {"emails": [], "org_ids": []}
    yield registry
    async with admin_sessions() as s, s.begin():
        if registry["org_ids"]:
            await s.execute(delete(Organization).where(Organization.id.in_(registry["org_ids"])))
        if registry["emails"]:
            emails = [e.lower() for e in registry["emails"]]
            await s.execute(delete(User).where(User.email.in_(emails)))


@pytest.fixture
async def admin_sessions() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(settings.DATABASE_URL_ADMIN)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


@pytest.fixture
async def two_orgs(
    admin_sessions: async_sessionmaker[AsyncSession],
) -> AsyncIterator[tuple[uuid.UUID, uuid.UUID]]:
    """Org A et org B, une intégration chacune ; supprimées en fin de test."""
    org_ids: list[uuid.UUID] = []
    async with admin_sessions() as s, s.begin():
        for tag in ("a", "b"):
            org = Organization(name=f"Org {tag.upper()}", slug=f"test-{tag}-{uuid.uuid4().hex[:8]}")
            s.add(org)
            await s.flush()
            s.add(
                Integration(
                    organization_id=org.id,
                    provider="salesforce",
                    encrypted_credentials=encrypt_credentials({"token": f"secret-{tag}"}),
                    instance_url=f"https://{tag}.example.com",
                )
            )
            org_ids.append(org.id)
    yield org_ids[0], org_ids[1]
    async with admin_sessions() as s, s.begin():
        # ondelete=CASCADE emporte les intégrations.
        await s.execute(delete(Organization).where(Organization.id.in_(org_ids)))
