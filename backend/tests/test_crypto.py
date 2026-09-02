"""Tests du chiffrement des credentials (critère 3 carte CORE, ADR-005)."""

import json
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.crypto import decrypt_credentials, encrypt_credentials
from app.core.models import Integration


def test_roundtrip_chiffrement() -> None:
    creds = {"access_token": "tok-123", "refresh_token": "ref-456"}
    token = encrypt_credentials(creds)
    assert decrypt_credentials(token) == creds


async def test_credentials_illisibles_en_base(
    two_orgs: tuple[uuid.UUID, uuid.UUID],
    admin_sessions: async_sessionmaker[AsyncSession],
) -> None:
    """Le bytea stocké ne contient ni le secret ni du JSON lisible ;
    seul le service sait le déchiffrer."""
    org_a, _ = two_orgs
    async with admin_sessions() as s:
        raw = (
            await s.execute(
                select(Integration.encrypted_credentials).where(
                    Integration.organization_id == org_a
                )
            )
        ).scalar_one()

    assert b"secret-a" not in raw
    try:
        json.loads(raw)
        readable = True
    except (ValueError, UnicodeDecodeError):
        readable = False
    assert not readable

    assert decrypt_credentials(raw) == {"token": "secret-a"}
