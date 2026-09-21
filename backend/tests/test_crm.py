"""Tests de la carte SALES OAuth : port CRM, client Salesforce, fabrique, flux.

Le réseau Salesforce est simulé par un mini-serveur REST (httpx.MockTransport)
adossé à un FakeCRM : les MÊMES tests d'interface s'exécutent contre FakeCRM
et contre SalesforceClient (critère 4). Base et RLS sont réels.
"""

import asyncio
import base64
import hashlib
import re
import uuid
from collections.abc import Callable
from types import SimpleNamespace
from typing import Any

import httpx
import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.crypto import decrypt_credentials, encrypt_credentials
from app.core.models import Integration
from app.sales.crm import CRMAuthError, CRMError, CRMPort, FakeCRM, SalesforceClient, get_crm
from app.sales.crm import salesforce as sf_module

_SOBJECT = re.compile(r"^/services/data/v60\.0/sobjects/(\w+)(?:/(\w+))?$")


class MiniSalesforce:
    """Mini-API REST Salesforce en mémoire (adossée à un FakeCRM)."""

    def __init__(self, valid_token: str = "tok-1") -> None:
        self.store = FakeCRM()
        self.valid_token = valid_token
        self.requests: list[str] = []

    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self._handle)

    async def _handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(f"{request.method} {request.url.path}")
        if request.headers.get("Authorization") != f"Bearer {self.valid_token}":
            return httpx.Response(401, json=[{"errorCode": "INVALID_SESSION_ID"}])

        path = request.url.path
        if path == "/services/data/v60.0/query":
            records = await self.store.query(request.url.params["q"])
            # `attributes` : métadonnées SF que le client doit retirer.
            records = [{"attributes": {"type": "x"}, **r} for r in records]
            return httpx.Response(200, json={"done": True, "records": records})

        match = _SOBJECT.match(path)
        assert match, f"chemin inattendu : {path}"
        object, id = match.group(1), match.group(2)
        try:
            if request.method == "POST":
                new_id = await self.store.create(object, _json(request))
                return httpx.Response(201, json={"id": new_id, "success": True})
            if request.method == "GET":
                record = await self.store.get(object, id or "")
                return httpx.Response(200, json={"attributes": {"type": object}, **record})
            if request.method == "PATCH":
                await self.store.update(object, id or "", _json(request))
                return httpx.Response(204)
        except CRMError:
            return httpx.Response(404, json=[{"errorCode": "NOT_FOUND"}])
        return httpx.Response(405)


def _json(request: httpx.Request) -> dict[str, Any]:
    import json

    return dict(json.loads(request.content))


@pytest.fixture(params=["fake", "salesforce"])
async def crm(request: pytest.FixtureRequest) -> Any:
    """Le même contrat, deux implémentations (critère 4)."""
    if request.param == "fake":
        yield FakeCRM()
        return
    server = MiniSalesforce()
    client = SalesforceClient(
        "https://sandbox.example.com", "tok-1", "refresh-1", transport=server.transport()
    )
    yield client
    await client.aclose()


async def test_interface_create_get_update_query(crm: CRMPort) -> None:
    id = await crm.create("Account", {"Name": "Miara SARL", "Industry": "SaaS"})
    assert id

    record = await crm.get("Account", id)
    assert record["Name"] == "Miara SARL" and record["Id"] == id
    assert "attributes" not in record  # métadonnées SF filtrées

    await crm.update("Account", id, {"Industry": "IA"})
    assert (await crm.get("Account", id))["Industry"] == "IA"

    await crm.create("Account", {"Name": "Autre SA", "Industry": "BTP"})
    rows = await crm.query("SELECT Id, Name FROM Account WHERE Industry = 'IA'")
    assert [r["Name"] for r in rows] == ["Miara SARL"]
    assert set(rows[0]) == {"Id", "Name"}


async def test_interface_get_inconnu_leve_crmerror(crm: CRMPort) -> None:
    with pytest.raises(CRMError):
        await crm.get("Account", "001INEXISTANT")


async def test_401_refresh_puis_rejeu_reussi(monkeypatch: pytest.MonkeyPatch) -> None:
    """Critère 2 : jeton expiré -> 401 -> refresh -> requête rejouée UNE fois."""
    server = MiniSalesforce(valid_token="tok-2")  # tok-1 est donc « expiré »
    refreshed: list[dict[str, Any]] = []

    async def fake_refresh(refresh_token: str) -> dict[str, Any]:
        assert refresh_token == "refresh-1"
        return {"access_token": "tok-2"}

    monkeypatch.setattr(sf_module, "refresh_access_token", fake_refresh)

    async def on_refresh(tokens: dict[str, Any]) -> None:
        refreshed.append(tokens)

    async with SalesforceClient(
        "https://sandbox.example.com",
        "tok-1",
        "refresh-1",
        on_refresh=on_refresh,
        transport=server.transport(),
    ) as client:
        id = await client.create("Contact", {"LastName": "Rakoto"})
        assert (await client.get("Contact", id))["LastName"] == "Rakoto"

    # 1er POST en 401 + rejeu, puis GET direct (jeton déjà rafraîchi).
    assert server.requests.count("POST /services/data/v60.0/sobjects/Contact") == 2
    assert refreshed == [{"access_token": "tok-2"}]  # persisté via le callback


async def test_requetes_paralleles_ne_rafraichissent_qu_une_fois(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Un seul échange de jeton pour N requêtes concurrentes expirées.

    L'outil composite lance 5 requêtes en parallèle : sans verrou, chacune
    échangerait le même refresh token. Salesforce faisant tourner ce jeton
    (rotation), les jetons obtenus en trop sont invalidés et celui persisté en
    base peut être mort — l'organisation perd sa connexion à l'expiration
    suivante. C'est exactement la panne observée sur le bac à sable.
    """
    server = MiniSalesforce(valid_token="tok-2")
    exchanges: list[str] = []
    persisted: list[dict[str, Any]] = []

    async def fake_refresh(refresh_token: str) -> dict[str, Any]:
        exchanges.append(refresh_token)
        # Rotation : l'ancien refresh token est invalidé par Salesforce.
        return {"access_token": "tok-2", "refresh_token": f"refresh-{len(exchanges) + 1}"}

    monkeypatch.setattr(sf_module, "refresh_access_token", fake_refresh)

    async def on_refresh(tokens: dict[str, Any]) -> None:
        persisted.append(tokens)

    async with SalesforceClient(
        "https://sandbox.example.com",
        "tok-1",
        "refresh-1",
        on_refresh=on_refresh,
        transport=server.transport(),
    ) as client:
        rows = await asyncio.gather(*(client.query(f"SELECT Id FROM Account{i}") for i in range(5)))

    assert len(rows) == 5
    assert exchanges == ["refresh-1"]  # un seul échange, pas cinq
    assert len(persisted) == 1  # une seule écriture en base, donc pas de jeton mort
    assert client._refresh_token == "refresh-2"  # rotation prise en compte


async def test_401_persistant_leve_crmautherror(monkeypatch: pytest.MonkeyPatch) -> None:
    """Le rejeu n'a lieu qu'une fois : 401 après refresh -> CRMAuthError."""
    server = MiniSalesforce(valid_token="jamais-bon")

    async def fake_refresh(refresh_token: str) -> dict[str, Any]:
        return {"access_token": "toujours-mauvais"}

    monkeypatch.setattr(sf_module, "refresh_access_token", fake_refresh)

    async with SalesforceClient(
        "https://sandbox.example.com", "tok-1", "refresh-1", transport=server.transport()
    ) as client:
        with pytest.raises(CRMAuthError):
            await client.query("SELECT Id FROM Account")
    assert len(server.requests) == 2  # jamais un 3e essai


async def test_org_a_ne_peut_pas_obtenir_le_client_de_org_b(
    two_orgs: tuple[uuid.UUID, uuid.UUID],
    admin_sessions: async_sessionmaker[AsyncSession],
) -> None:
    """Critère 3 : la fabrique ne sert QUE l'intégration de l'org du contexte."""
    org_a, org_b = two_orgs
    async with admin_sessions() as s, s.begin():
        for org_id, tag in ((org_a, "a"), (org_b, "b")):
            row = (
                await s.execute(select(Integration).where(Integration.organization_id == org_id))
            ).scalar_one()
            row.encrypted_credentials = encrypt_credentials(
                {
                    "access_token": f"tok-{tag}",
                    "refresh_token": f"refresh-{tag}",
                    "instance_url": f"https://{tag}.example.com",
                }
            )

    client_a = await get_crm(SimpleNamespace(org_id=org_a))
    client_b = await get_crm(SimpleNamespace(org_id=org_b))
    assert isinstance(client_a, SalesforceClient) and isinstance(client_b, SalesforceClient)
    assert client_a is not client_b  # jamais de client partagé entre orgs
    assert client_a._instance_url == "https://a.example.com"
    assert client_b._instance_url == "https://b.example.com"
    await client_a.aclose()
    await client_b.aclose()

    # Org sans intégration : rien à servir (le RLS a déjà filtré la ligne de A).
    async with admin_sessions() as s, s.begin():
        await s.execute(delete(Integration).where(Integration.organization_id == org_b))
    with pytest.raises(CRMAuthError):
        await get_crm(SimpleNamespace(org_id=org_b))


async def test_parcours_oauth_callback_stocke_les_jetons_chiffres(
    make_client: Callable[[], httpx.AsyncClient],
    admin_sessions: async_sessionmaker[AsyncSession],
    auth_cleanup: dict,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Critère 1 (backend) : connect -> consentement -> callback -> jetons
    chiffrés dans `integrations`. L'échange de code est simulé ; le parcours
    sur bac à sable réel se valide à la main avec la Connected App."""
    client = make_client()
    email = f"sf-admin-{uuid.uuid4().hex[:8]}@test.miara.dev"
    auth_cleanup["emails"].append(email)
    r = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "correct-horse-42", "full_name": "SF Admin"},
    )
    assert r.status_code == 201
    r = await client.post("/api/v1/orgs", json={"name": "SF Corp"})
    assert r.status_code == 201
    org_id = r.json()["id"]
    auth_cleanup["org_ids"].append(org_id)

    # /connect : redirection vers Salesforce avec state signé + challenge PKCE.
    monkeypatch.setattr(sf_module.settings, "SF_CLIENT_ID", "test-client-id")
    monkeypatch.setattr(sf_module.settings, "SF_CLIENT_SECRET", "test-secret")
    r = await client.get("/api/v1/integrations/salesforce/connect", follow_redirects=False)
    assert r.status_code == 302
    location = httpx.URL(r.headers["location"])
    assert str(location).startswith(f"{sf_module.settings.SF_LOGIN_URL}/services/oauth2/authorize")
    assert location.params["client_id"] == "test-client-id"
    assert location.params["code_challenge_method"] == "S256"
    state = location.params["state"]
    challenge = location.params["code_challenge"]

    # /callback : échange simulé — le verifier PKCE (Redis, jamais passé au
    # navigateur) doit correspondre au challenge envoyé à Salesforce.
    async def fake_exchange(code: str, code_verifier: str) -> dict[str, Any]:
        assert code == "CODE123"
        digest = hashlib.sha256(code_verifier.encode()).digest()
        assert base64.urlsafe_b64encode(digest).rstrip(b"=").decode() == challenge
        return {
            "access_token": "sf-access",
            "refresh_token": "sf-refresh",
            "instance_url": "https://miara-dev-ed.sandbox.my.salesforce.com",
        }

    monkeypatch.setattr("app.sales.integrations.salesforce.exchange_code", fake_exchange)
    r = await client.get(
        f"/api/v1/integrations/salesforce/callback?code=CODE123&state={state}",
        follow_redirects=False,
    )
    assert r.status_code == 302
    assert r.headers["location"] == "/?salesforce=connected"

    # Rejeu du même state : le verifier a été consommé (GETDEL) -> 400.
    r = await client.get(
        f"/api/v1/integrations/salesforce/callback?code=CODE123&state={state}",
        follow_redirects=False,
    )
    assert r.status_code == 400

    # Jetons chiffrés en base, jamais exposés par GET /integrations.
    async with admin_sessions() as s:
        row = (
            await s.execute(
                select(Integration).where(Integration.organization_id == uuid.UUID(org_id))
            )
        ).scalar_one()
    assert decrypt_credentials(row.encrypted_credentials) == {
        "access_token": "sf-access",
        "refresh_token": "sf-refresh",
        "instance_url": "https://miara-dev-ed.sandbox.my.salesforce.com",
    }
    assert b"sf-access" not in row.encrypted_credentials

    r = await client.get("/api/v1/integrations")
    assert r.status_code == 200
    listed = r.json()
    assert listed == [
        {
            "provider": "salesforce",
            "instance_url": "https://miara-dev-ed.sandbox.my.salesforce.com",
            "status": "connected",
        }
    ]

    # State falsifié ou expiré : 400, rien n'est stocké.
    r = await client.get(
        "/api/v1/integrations/salesforce/callback?code=CODE123&state=forge",
        follow_redirects=False,
    )
    assert r.status_code == 400

    # Déconnexion : la ligne disparaît (révocation best-effort simulée).
    async def fake_revoke(token: str) -> None:
        assert token == "sf-refresh"

    monkeypatch.setattr("app.sales.integrations.salesforce.revoke_token", fake_revoke)
    r = await client.post("/api/v1/integrations/salesforce/disconnect")
    assert r.status_code == 200
    assert (await client.get("/api/v1/integrations")).json() == []
