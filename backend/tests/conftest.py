"""Fixtures partagées : sessions admin (BYPASSRLS), données A/B, clients HTTP,
passerelle LLM scriptée et organisation commerciale branchée sur un FakeCRM."""

import json
import uuid
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from typing import Annotated, Any

import httpx
import pytest
from fastapi import APIRouter, Depends
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.auth.deps import RequestContext, get_context
from app.auth.models import Organization, User
from app.config import settings
from app.core.crypto import encrypt_credentials
from app.core.llm import LLMResult, gateway_dependency
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
async def seeded_org(
    admin_sessions: async_sessionmaker[AsyncSession],
) -> AsyncIterator[tuple[uuid.UUID, dict[str, str]]]:
    """Org avec une intégration `mode=fake` et un FakeCRM peuplé du jeu de démo
    (outils sales). Nettoie l'org et le fake en fin de test."""
    from app.sales.crm import FakeCRM, clear_fake, register_fake
    from app.sales.tools.demo_data import seed_demo

    org_id = uuid.uuid4()
    async with admin_sessions() as s, s.begin():
        s.add(Organization(id=org_id, name="Tool Org", slug=f"tool-{uuid.uuid4().hex[:8]}"))
        s.add(
            Integration(
                organization_id=org_id,
                provider="salesforce",
                encrypted_credentials=encrypt_credentials({"mode": "fake"}),
                instance_url=None,
            )
        )
    crm = FakeCRM()
    ids = await seed_demo(crm)
    register_fake(org_id, crm)
    try:
        yield org_id, ids
    finally:
        clear_fake(org_id)
        async with admin_sessions() as s, s.begin():
            await s.execute(delete(Organization).where(Organization.id == org_id))


# --- passerelle LLM scriptée --------------------------------------------


@dataclass
class Step:
    """Une réponse du modèle : du texte, ou des appels d'outils."""

    content: str | None = None
    tool_calls: list[dict[str, Any]] | None = None


class ScriptedGateway:
    """Passerelle LLM déterministe : rejoue un script d'étapes, retient les
    alias demandés (escalade route → synthesize) et les messages envoyés."""

    def __init__(self, *steps: Step) -> None:
        self.steps = list(steps)
        self.aliases: list[str] = []
        self.tool_schemas: list[dict[str, Any]] | None = None
        self.messages: list[list[dict[str, Any]]] = []

    async def complete(
        self,
        alias: str,
        messages: Any,
        *,
        ctx: Any,
        tools: list[dict[str, Any]] | None = None,
        response_model: Any = None,
    ) -> LLMResult:
        self.aliases.append(alias)
        self.tool_schemas = tools
        self.messages.append([dict(m) for m in messages])
        step = self.steps.pop(0)
        parsed = None
        if response_model is not None and step.content and not step.tool_calls:
            # Même contrat que la vraie passerelle : la sortie structurée est
            # validée avant d'être rendue à l'appelant.
            parsed = response_model.model_validate_json(step.content)
        return LLMResult(
            content=step.content,
            parsed=parsed,
            tool_calls=step.tool_calls,
            model_used="scripted",
            input_tokens=10,
            output_tokens=5,
            latency_ms=1,
            cost_usd=None,
            trace_id=ctx.trace_id,
        )


def tool_call(id: str, tool: str, /, **args: Any) -> dict[str, Any]:
    """Appel d'outil émis par le modèle (positionnels : `name` est un argument
    d'outil possible)."""
    return {"id": id, "name": tool, "arguments": json.dumps(args)}


@pytest.fixture
def scripted() -> AsyncIterator[Callable[..., ScriptedGateway]]:
    """Installe une passerelle scriptée à la place de la vraie (DI FastAPI)."""

    def _install(*steps: Step) -> ScriptedGateway:
        gateway = ScriptedGateway(*steps)
        app.dependency_overrides[gateway_dependency] = lambda: gateway
        return gateway

    yield _install
    app.dependency_overrides.pop(gateway_dependency, None)


@pytest.fixture
async def sales_client(
    make_client: Callable[[], httpx.AsyncClient],
    admin_sessions: async_sessionmaker[AsyncSession],
    auth_cleanup: dict[str, list],
) -> AsyncIterator[tuple[httpx.AsyncClient, uuid.UUID, dict[str, str]]]:
    """Commercial authentifié dans une org branchée sur un FakeCRM peuplé."""
    from app.sales.crm import FakeCRM, clear_fake, register_fake
    from app.sales.tools.demo_data import seed_demo

    client = make_client()
    email = f"vendeur-{uuid.uuid4().hex[:8]}@test.miara.dev"
    auth_cleanup["emails"].append(email)
    r = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "correct-horse-42", "full_name": "Vendeur"},
    )
    assert r.status_code == 201
    r = await client.post("/api/v1/orgs", json={"name": "Vente Corp"})
    assert r.status_code == 201
    org_id = uuid.UUID(r.json()["id"])
    auth_cleanup["org_ids"].append(str(org_id))

    async with admin_sessions() as s, s.begin():
        s.add(
            Integration(
                organization_id=org_id,
                provider="salesforce",
                encrypted_credentials=encrypt_credentials({"mode": "fake"}),
                instance_url=None,
            )
        )
    crm = FakeCRM()
    ids = await seed_demo(crm)
    register_fake(org_id, crm)
    try:
        yield client, org_id, ids
    finally:
        clear_fake(org_id)


@pytest.fixture
async def hr_client(
    make_client: Callable[[], httpx.AsyncClient],
    auth_cleanup: dict[str, list],
    tmp_path_factory: pytest.TempPathFactory,
) -> AsyncIterator[tuple[httpx.AsyncClient, uuid.UUID]]:
    """Recruteur authentifié dans une org neuve, avec un stockage de CV isolé.

    Le `FileStore` est surchargé par injection : les tests n'écrivent jamais
    dans le vrai dossier de stockage, et le dossier temporaire disparaît avec
    la session pytest.
    """
    from app.hr.storage import FileStore, get_file_store

    client = make_client()
    email = f"rh-{uuid.uuid4().hex[:8]}@test.miara.dev"
    auth_cleanup["emails"].append(email)
    r = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "correct-horse-42", "full_name": "Recruteuse"},
    )
    assert r.status_code == 201
    r = await client.post("/api/v1/orgs", json={"name": "RH Corp"})
    assert r.status_code == 201
    org_id = uuid.UUID(r.json()["id"])
    auth_cleanup["org_ids"].append(str(org_id))

    store = FileStore(tmp_path_factory.mktemp("cv-store"))
    app.dependency_overrides[get_file_store] = lambda: store
    try:
        yield client, org_id
    finally:
        app.dependency_overrides.pop(get_file_store, None)


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
