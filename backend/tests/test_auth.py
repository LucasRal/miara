"""Tests d'intégration de la carte auth (critères d'acceptation 1 à 3).

Vraie base PostgreSQL (RLS actif, rôle miara_app) + vrai Redis. Chaque test
utilise des emails uniques et nettoie ses données via `auth_cleanup`.
"""

import uuid
from collections.abc import Callable

import httpx
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.auth.models import Membership
from app.core.crypto import encrypt_credentials
from app.core.models import Integration

PASSWORD = "correct-horse-42"


def _email(tag: str) -> str:
    return f"{tag}-{uuid.uuid4().hex[:8]}@test.miara.dev"


async def _register(client: httpx.AsyncClient, email: str, name: str = "Test User") -> dict:
    r = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": PASSWORD, "full_name": name},
    )
    assert r.status_code == 201, r.text
    return r.json()


async def _create_org(client: httpx.AsyncClient, name: str) -> dict:
    r = await client.post("/api/v1/orgs", json={"name": name})
    assert r.status_code == 201, r.text
    return r.json()


async def test_parcours_inscription_puis_creation_org(
    make_client: Callable[[], httpx.AsyncClient], auth_cleanup: dict
) -> None:
    """Backend du critère 4 : inscription -> création d'org -> contexte actif."""
    client = make_client()
    email = _email("owner")
    auth_cleanup["emails"].append(email)

    me = await _register(client, email, "Alice Own")
    assert me["org_id"] is None and me["memberships"] == []

    org = await _create_org(client, "Aventures SARL")
    auth_cleanup["org_ids"].append(org["id"])

    r = await client.get("/api/v1/me")
    assert r.status_code == 200
    me = r.json()
    assert me["org_id"] == org["id"]
    assert me["role"] == "owner"
    assert [m["organization_id"] for m in me["memberships"]] == [org["id"]]


async def test_switch_change_les_donnees_visibles(
    make_client: Callable[[], httpx.AsyncClient],
    admin_sessions: async_sessionmaker[AsyncSession],
    auth_cleanup: dict,
) -> None:
    """Critère 1 : membre de 2 orgs, données différentes après /switch (RLS)."""
    client = make_client()
    email = _email("dual")
    auth_cleanup["emails"].append(email)
    await _register(client, email)

    org1 = await _create_org(client, "Org Une")
    org2 = await _create_org(client, "Org Deux")
    auth_cleanup["org_ids"] += [org1["id"], org2["id"]]

    async with admin_sessions() as s, s.begin():
        for org, url in ((org1, "https://one.example.com"), (org2, "https://two.example.com")):
            s.add(
                Integration(
                    organization_id=uuid.UUID(org["id"]),
                    provider="salesforce",
                    encrypted_credentials=encrypt_credentials({"token": "t"}),
                    instance_url=url,
                )
            )

    # Contexte actif = org2 (dernière créée).
    r = await client.get("/api/v1/_test/integrations")
    assert r.status_code == 200
    assert r.json() == ["https://two.example.com"]

    r = await client.post(f"/api/v1/orgs/{org1['id']}/switch")
    assert r.status_code == 200
    assert r.json()["org_id"] == org1["id"]

    r = await client.get("/api/v1/_test/integrations")
    assert r.json() == ["https://one.example.com"]


async def test_hr_interdit_sur_endpoint_sales(
    make_client: Callable[[], httpx.AsyncClient], auth_cleanup: dict
) -> None:
    """Critère 2 : un rôle hr sur un endpoint sales -> 403 (owner -> 200)."""
    owner, member = make_client(), make_client()
    owner_email, member_email = _email("owner"), _email("hr")
    auth_cleanup["emails"] += [owner_email, member_email]

    await _register(owner, owner_email)
    org = await _create_org(owner, "RH Corp")
    auth_cleanup["org_ids"].append(org["id"])
    await _register(member, member_email)

    r = await owner.post(
        f"/api/v1/orgs/{org['id']}/invite", json={"email": member_email, "role": "hr"}
    )
    assert r.status_code == 201, r.text

    # Le membre se (re)connecte : son contexte actif devient l'org rejointe.
    r = await member.post("/api/v1/auth/login", json={"email": member_email, "password": PASSWORD})
    assert r.status_code == 200 and r.json()["role"] == "hr"

    assert (await member.get("/api/v1/sales/ping")).status_code == 403
    assert (await owner.get("/api/v1/sales/ping")).status_code == 200


async def test_refresh_revoque_et_rotation(
    make_client: Callable[[], httpx.AsyncClient], auth_cleanup: dict
) -> None:
    """Critère 3a : refresh révoqué (logout) -> 401 ; jeton rejoué -> 401."""
    client = make_client()
    email = _email("refresh")
    auth_cleanup["emails"].append(email)
    await _register(client, email)

    first_refresh = client.cookies.get("refresh")
    assert first_refresh

    # Rotation : un refresh réussit, rejouer l'ancien jeton échoue.
    assert (await client.post("/api/v1/auth/refresh")).status_code == 200
    replay = make_client()
    replay.cookies.set("refresh", first_refresh, domain="test", path="/api/v1/auth")
    assert (await replay.post("/api/v1/auth/refresh")).status_code == 401

    # Révocation : logout puis réutilisation du jeton courant -> 401.
    current_refresh = client.cookies.get("refresh")
    assert (await client.post("/api/v1/auth/logout")).status_code == 204
    revoked = make_client()
    revoked.cookies.set("refresh", current_refresh, domain="test", path="/api/v1/auth")
    assert (await revoked.post("/api/v1/auth/refresh")).status_code == 401


async def test_sixieme_tentative_de_login_429(
    make_client: Callable[[], httpx.AsyncClient], auth_cleanup: dict
) -> None:
    """Critère 3b : 5 tentatives / 15 min par email+IP, la 6e -> 429."""
    client = make_client()
    email = _email("bruteforce")
    auth_cleanup["emails"].append(email)
    await _register(client, email)

    for _ in range(5):
        r = await client.post(
            "/api/v1/auth/login", json={"email": email, "password": "mauvais-mdp"}
        )
        assert r.status_code == 401
    # 6e tentative bloquée, même avec le BON mot de passe.
    r = await client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    assert r.status_code == 429


async def test_membership_revoquee_invalide_le_token(
    make_client: Callable[[], httpx.AsyncClient],
    admin_sessions: async_sessionmaker[AsyncSession],
    auth_cleanup: dict,
) -> None:
    """La membership est relue en base : supprimée -> le JWT encore valide est refusé."""
    client = make_client()
    email = _email("revoked")
    auth_cleanup["emails"].append(email)
    me = await _register(client, email)
    org = await _create_org(client, "Éphémère SAS")
    auth_cleanup["org_ids"].append(org["id"])
    assert (await client.get("/api/v1/sales/ping")).status_code == 200

    async with admin_sessions() as s, s.begin():
        await s.execute(delete(Membership).where(Membership.user_id == uuid.UUID(me["id"])))

    assert (await client.get("/api/v1/sales/ping")).status_code == 401


async def _login(client: httpx.AsyncClient, email: str) -> None:
    r = await client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    assert r.status_code == 200, r.text


async def test_membres_listes_et_role_modifiable(
    make_client: Callable[[], httpx.AsyncClient], auth_cleanup: dict
) -> None:
    """Page Paramètres : lister les membres, changer un rôle (owner/admin)."""
    owner, second = make_client(), make_client()
    owner_email, second_email = _email("owner"), _email("collab")
    auth_cleanup["emails"] += [owner_email, second_email]

    await _register(second, second_email, "Bob Collab")
    await _register(owner, owner_email, "Alice Own")
    org = await _create_org(owner, "Membres SARL")
    auth_cleanup["org_ids"].append(org["id"])

    r = await owner.post(
        f"/api/v1/orgs/{org['id']}/invite", json={"email": second_email, "role": "hr"}
    )
    assert r.status_code == 201, r.text

    r = await owner.get(f"/api/v1/orgs/{org['id']}/members")
    assert r.status_code == 200
    membres = {m["email"]: m["role"] for m in r.json()}
    assert membres == {owner_email: "owner", second_email: "hr"}

    bob_id = next(m["user_id"] for m in r.json() if m["email"] == second_email)
    r = await owner.patch(f"/api/v1/orgs/{org['id']}/members/{bob_id}", json={"role": "sales"})
    assert r.status_code == 200 and r.json()["role"] == "sales"

    # Le rôle relu en base à chaque requête : Bob voit immédiatement sales.
    await _login(second, second_email)
    assert (await second.get("/api/v1/me")).json()["role"] == "sales"


async def test_garde_fous_sur_les_roles(
    make_client: Callable[[], httpx.AsyncClient], auth_cleanup: dict
) -> None:
    """Pas d'auto-modification, pas de retrait du dernier owner, pas de rôle par un non-admin."""
    owner, admin, hr = make_client(), make_client(), make_client()
    emails = [_email("owner"), _email("admin"), _email("hr")]
    auth_cleanup["emails"] += emails
    for client, email in zip((admin, hr), emails[1:], strict=True):
        await _register(client, email, "Membre")
    await _register(owner, emails[0], "Alice Own")
    org = await _create_org(owner, "Gardes SARL")
    auth_cleanup["org_ids"].append(org["id"])
    for email, role in ((emails[1], "admin"), (emails[2], "hr")):
        r = await owner.post(
            f"/api/v1/orgs/{org['id']}/invite", json={"email": email, "role": role}
        )
        assert r.status_code == 201, r.text

    membres = {
        m["email"]: m["user_id"]
        for m in (await owner.get(f"/api/v1/orgs/{org['id']}/members")).json()
    }
    owner_id, admin_id, hr_id = membres[emails[0]], membres[emails[1]], membres[emails[2]]

    # 1. Son propre rôle : refusé (évite qu'un owner se verrouille dehors).
    r = await owner.patch(f"/api/v1/orgs/{org['id']}/members/{owner_id}", json={"role": "sales"})
    assert r.status_code == 409

    # 2. L'admin ne peut pas rétrograder le SEUL owner.
    await _login(admin, emails[1])
    r = await admin.patch(f"/api/v1/orgs/{org['id']}/members/{owner_id}", json={"role": "sales"})
    assert r.status_code == 409
    assert "owner" in r.json()["detail"]

    # 3. Un rôle métier ne gère pas les membres, mais peut les lister.
    await _login(hr, emails[2])
    r = await hr.patch(f"/api/v1/orgs/{org['id']}/members/{admin_id}", json={"role": "sales"})
    assert r.status_code == 403
    assert (await hr.get(f"/api/v1/orgs/{org['id']}/members")).status_code == 200

    # 4. L'org de l'URL doit être celle du contexte actif.
    r = await owner.get(f"/api/v1/orgs/{uuid.uuid4()}/members")
    assert r.status_code == 403
    assert hr_id  # identité relue plus haut


async def test_retrait_d_un_membre_et_ses_garde_fous(
    make_client: Callable[[], httpx.AsyncClient], auth_cleanup: dict
) -> None:
    """Retirer quelqu'un qui part : possible ; se retirer ou vider les owners : non."""
    owner, second = make_client(), make_client()
    owner_email, second_email = _email("owner"), _email("partant")
    auth_cleanup["emails"] += [owner_email, second_email]

    await _register(second, second_email, "Bob Partant")
    await _register(owner, owner_email, "Alice Own")
    org = await _create_org(owner, "Retraits SARL")
    auth_cleanup["org_ids"].append(org["id"])
    r = await owner.post(
        f"/api/v1/orgs/{org['id']}/invite", json={"email": second_email, "role": "sales"}
    )
    assert r.status_code == 201, r.text

    membres = {
        m["email"]: m["user_id"]
        for m in (await owner.get(f"/api/v1/orgs/{org['id']}/members")).json()
    }
    owner_id, bob_id = membres[owner_email], membres[second_email]

    # 1. Se retirer soi-même : refusé (personne ne se verrouille dehors).
    assert (await owner.delete(f"/api/v1/orgs/{org['id']}/members/{owner_id}")).status_code == 409

    # 2. Retirer le membre : accepté, et il disparaît de la liste.
    assert (await owner.delete(f"/api/v1/orgs/{org['id']}/members/{bob_id}")).status_code == 204
    restants = (await owner.get(f"/api/v1/orgs/{org['id']}/members")).json()
    assert [m["email"] for m in restants] == [owner_email]

    # 3. Le rôle est relu à chaque requête : Bob perd l'accès immédiatement.
    await _login(second, second_email)
    assert (await second.get(f"/api/v1/orgs/{org['id']}/members")).status_code in (401, 403)

    # 4. Membre inconnu : 404, pas 204 silencieux.
    assert (
        await owner.delete(f"/api/v1/orgs/{org['id']}/members/{uuid.uuid4()}")
    ).status_code == 404
