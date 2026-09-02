"""Tests d'isolation multi-locataire par RLS (critères carte CORE).

Exécutés contre la base PostgreSQL locale : le runtime (`tenant_session` /
`async_session`) se connecte en `miara_app` (soumis aux politiques RLS) ;
la préparation et le nettoyage passent par `miara_admin` (BYPASSRLS).
"""

import uuid

from sqlalchemy import select

from app.core.db import async_session
from app.core.models import Integration
from app.core.tenant import tenant_session


async def test_isolation_par_organisation(two_orgs: tuple[uuid.UUID, uuid.UUID]) -> None:
    """Critère 1 : connecté en A -> 1 ligne, en B -> 1 ligne, sans org -> 0."""
    org_a, org_b = two_orgs

    for org_id in (org_a, org_b):
        async with tenant_session(org_id) as s:
            rows = (await s.execute(select(Integration))).scalars().all()
            assert len(rows) == 1
            assert rows[0].organization_id == org_id

    # Sans app.current_org posé : aucune ligne visible, quelle que soit la table.
    async with async_session() as s:
        rows = (await s.execute(select(Integration))).scalars().all()
        assert rows == []


async def test_requete_sans_filtre_ne_voit_jamais_l_autre_org(
    two_orgs: tuple[uuid.UUID, uuid.UUID],
) -> None:
    """Critère 2 : preuve RLS - un SELECT ORM sans aucun filtre ne fuit pas."""
    org_a, org_b = two_orgs

    async with tenant_session(org_a) as s:
        visible = {
            row.organization_id for row in (await s.execute(select(Integration))).scalars()
        }

    assert org_b not in visible
    assert visible == {org_a}
