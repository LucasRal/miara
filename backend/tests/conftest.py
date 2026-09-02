"""Fixtures partagées : sessions admin (BYPASSRLS) et données de test A/B."""

import uuid
from collections.abc import AsyncIterator

import pytest
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.auth.models import Organization
from app.config import settings
from app.core.crypto import encrypt_credentials
from app.core.models import Integration


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
