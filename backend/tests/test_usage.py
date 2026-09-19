"""Test du critère « GET /usage : tokens et coût de l'org courante uniquement »."""

import uuid
from collections.abc import Callable
from decimal import Decimal

import httpx
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.auth.models import Organization
from app.core.models import LLMCall

PASSWORD = "correct-horse-42"


def _call(org_id: uuid.UUID, alias: str, tokens: int, cost: str) -> LLMCall:
    return LLMCall(
        organization_id=org_id,
        trace_id=uuid.uuid4(),
        agent="test",
        alias=alias,
        model_used="mock",
        input_tokens=tokens,
        output_tokens=tokens // 2,
        latency_ms=100,
        cost_usd=Decimal(cost),
        status="ok",
    )


async def test_usage_ne_voit_que_l_org_courante(
    make_client: Callable[[], httpx.AsyncClient],
    admin_sessions: async_sessionmaker[AsyncSession],
    auth_cleanup: dict,
) -> None:
    client = make_client()
    email = f"usage-{uuid.uuid4().hex[:8]}@test.miara.dev"
    auth_cleanup["emails"].append(email)
    r = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": PASSWORD, "full_name": "Usage Tester"},
    )
    assert r.status_code == 201
    r = await client.post("/api/v1/orgs", json={"name": "Org Usage"})
    assert r.status_code == 201
    my_org = uuid.UUID(r.json()["id"])
    auth_cleanup["org_ids"].append(my_org)

    async with admin_sessions() as s, s.begin():
        other = Organization(name="Org Étrangère", slug=f"etrangere-{uuid.uuid4().hex[:8]}")
        s.add(other)
        await s.flush()
        auth_cleanup["org_ids"].append(other.id)
        s.add(_call(my_org, "hr.score", tokens=1000, cost="0.010000"))
        s.add(_call(my_org, "sales.route", tokens=200, cost="0.000500"))
        # Gros volume dans l'autre org : ne doit JAMAIS apparaître.
        s.add(_call(other.id, "hr.score", tokens=999999, cost="42.000000"))

    r = await client.get("/api/v1/usage")
    assert r.status_code == 200
    data = r.json()
    assert data["organization_id"] == str(my_org)
    assert data["total_calls"] == 2
    assert data["input_tokens"] == 1200
    assert data["output_tokens"] == 600
    assert data["cost_usd"] == 0.0105
    assert {a["alias"] for a in data["by_alias"]} == {"hr.score", "sales.route"}
