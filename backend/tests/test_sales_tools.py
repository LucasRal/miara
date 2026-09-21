"""Tests de la carte [SALES] outils de lecture (contre FakeCRM).

Chaque outil est appelé via son handler avec un vrai RequestContext d'agent ;
`get_crm` renvoie un FakeCRM peuplé du jeu de démo (mode `fake`), l'org et
l'intégration existent en base sous RLS.
"""

import json
import time
import uuid

from app.core.agents.context import RequestContext
from app.sales.tools import (
    READ_TOOLS,
    find_account,
    find_contact,
    get_account_context,
    get_opportunity,
    search_activities,
)
from app.sales.tools.cache import invalidate
from app.sales.tools.read import GetAccountContextArgs, fetch_account_context


def _ctx(org_id: uuid.UUID) -> RequestContext:
    return RequestContext(org_id=org_id, user_id=uuid.uuid4(), role="sales")


async def test_find_account(seeded_org: tuple[uuid.UUID, dict[str, str]]) -> None:
    org_id, ids = seeded_org
    result = await find_account.run(find_account.args_schema(name="Tech"), _ctx(org_id))
    assert [a["name"] for a in result] == ["TechStart SAS"]
    assert result[0]["id"] == ids["techstart"]
    assert result[0]["industry"] == "Logiciel"


async def test_find_contact_avec_desambiguisation(
    seeded_org: tuple[uuid.UUID, dict[str, str]],
) -> None:
    org_id, ids = seeded_org
    ctx = _ctx(org_id)

    hanta = await find_contact.run(find_contact.args_schema(name="Razafy"), ctx)
    assert len(hanta) == 1 and hanta[0]["id"] == ids["razafy"]
    assert hanta[0]["account_id"] == ids["techstart"]

    # "Martin" existe chez Globex, pas chez TechStart : le filtre compte tranche.
    globex = await find_contact.run(
        find_contact.args_schema(name="Martin", account_name="Globex"), ctx
    )
    assert [c["name"] for c in globex] == ["Paul Martin"]
    none = await find_contact.run(
        find_contact.args_schema(name="Martin", account_name="TechStart"), ctx
    )
    assert none == []


async def test_get_opportunity(seeded_org: tuple[uuid.UUID, dict[str, str]]) -> None:
    org_id, ids = seeded_org
    opp = await get_opportunity.run(
        get_opportunity.args_schema(opportunity_id=ids["opp_open"]), _ctx(org_id)
    )
    assert opp["id"] == ids["opp_open"]
    assert opp["stage"] == "Proposition"
    assert opp["amount"] == 48000.0


async def test_get_opportunity_par_nom_et_homonymes(
    seeded_org: tuple[uuid.UUID, dict[str, str]],
) -> None:
    """Résolution par nom : un seul appel d'outil au lieu de deux. En cas
    d'homonymes, les candidates sont rendues avec leurs ids."""
    from app.sales.crm.factory import _fakes

    org_id, ids = seeded_org
    ctx = _ctx(org_id)

    found = await get_opportunity.run(
        get_opportunity.args_schema(opportunity_name="Licences"), ctx
    )
    assert found["id"] == ids["opp_open"] and found["stage"] == "Proposition"

    absent = await get_opportunity.run(
        get_opportunity.args_schema(opportunity_name="Inexistante"), ctx
    )
    assert "error" in absent

    await _fakes[org_id].create(
        "Opportunity",
        {"Name": "TechStart - Licences 2027", "StageName": "Prospection", "IsClosed": False},
    )
    # Le cache de 60 s servirait la réponse précédente : on le purge ici.
    args = get_opportunity.args_schema(opportunity_name="Licences")
    await invalidate(org_id, "get_opportunity", args)
    ambigu = await get_opportunity.run(
        get_opportunity.args_schema(opportunity_name="Licences"), ctx
    )
    assert len(ambigu["candidates"]) == 2
    assert ids["opp_open"] in [c["id"] for c in ambigu["candidates"]]


async def test_get_account_context_resout_le_nom_du_compte(
    seeded_org: tuple[uuid.UUID, dict[str, str]],
) -> None:
    org_id, ids = seeded_org
    ctx = _ctx(org_id)

    result = await get_account_context.run(
        get_account_context.args_schema(account_name="TechStart"), ctx
    )
    assert ids["techstart"] in result["context"]

    absent = await get_account_context.run(
        get_account_context.args_schema(account_name="Inconnue SARL"), ctx
    )
    assert "error" in absent and "context" not in absent


async def test_search_activities_fenetre(seeded_org: tuple[uuid.UUID, dict[str, str]]) -> None:
    org_id, ids = seeded_org
    ctx = _ctx(org_id)

    recent = await search_activities.run(
        search_activities.args_schema(record_id=ids["techstart"], days=30), ctx
    )
    # 1 tâche récente + 1 événement récent ; la tâche vieille de 200 j est exclue.
    assert len(recent) == 2
    assert {a["type"] for a in recent} == {"Task", "Event"}

    wide = await search_activities.run(
        search_activities.args_schema(record_id=ids["techstart"], days=365), ctx
    )
    assert len(wide) == 3  # la vieille activité réapparaît
    # Tri décroissant par date.
    dates = [a["date"] for a in wide]
    assert dates == sorted(dates, reverse=True)


async def test_get_account_context_composite(
    seeded_org: tuple[uuid.UUID, dict[str, str]],
) -> None:
    """Données structurées du composite (la mise en forme sous budget est
    testée dans test_sales_assistant.py)."""
    org_id, ids = seeded_org
    args = get_account_context.args_schema(account_id=ids["techstart"])
    assert isinstance(args, GetAccountContextArgs)
    ctx = await fetch_account_context(args, _ctx(org_id))
    assert ctx["account"]["name"] == "TechStart SAS"
    assert [c["id"] for c in ctx["contacts"]] == [ids["razafy"]]
    # Seules les opportunités et cas OUVERTS.
    assert [o["id"] for o in ctx["open_opportunities"]] == [ids["opp_open"]]
    assert [c["id"] for c in ctx["open_cases"]] == [ids["case_open"]]
    assert len(ctx["recent_activities"]) == 2  # fenêtre 90 j par défaut


async def test_get_account_context_rend_du_texte_au_modele(
    seeded_org: tuple[uuid.UUID, dict[str, str]],
) -> None:
    """L'outil composite répond au modèle en texte compact passé par le
    ContextBuilder — pas en JSON brut — avec les ids et les compteurs."""
    org_id, ids = seeded_org
    result = await get_account_context.run(
        get_account_context.args_schema(account_id=ids["techstart"]), _ctx(org_id)
    )
    assert set(result) == {"context", "tokens_used", "items_dropped"}
    text = result["context"]
    assert "TechStart SAS" in text and ids["techstart"] in text
    assert ids["opp_open"] in text and ids["razafy"] in text and ids["case_open"] in text
    assert result["items_dropped"] == 0 and result["tokens_used"] > 0


async def test_schemas_outils_valides_pour_le_modele() -> None:
    """Critère : le schéma JSON exporté de chaque outil est exploitable."""
    for tool in READ_TOOLS:
        schema = tool.to_llm_schema()
        assert schema["type"] == "function"
        fn = schema["function"]
        assert fn["name"] == tool.name and fn["description"]
        params = fn["parameters"]
        assert params["type"] == "object" and "properties" in params
        json.dumps(schema)  # sérialisable pour l'API d'outils


async def test_cache_deuxieme_appel_rapide_et_memorise(
    seeded_org: tuple[uuid.UUID, dict[str, str]],
) -> None:
    """Critère cache : 2e appel identique servi depuis Redis (< 50 ms), donc
    insensible à une modification du CRM entre les deux appels."""
    org_id, ids = seeded_org
    ctx = _ctx(org_id)
    args = find_account.args_schema(name="Tech")

    first = await find_account.run(args, ctx)
    assert [a["name"] for a in first] == ["TechStart SAS"]

    # On ajoute un compte qui matcherait : s'il apparaît, c'est que le cache
    # a été contourné.
    from app.sales.crm.factory import _fakes

    await _fakes[org_id].create("Account", {"Name": "TechStart Two"})

    start = time.perf_counter()
    second = await find_account.run(args, ctx)
    elapsed = time.perf_counter() - start
    assert second == first  # résultat mémorisé, pas le nouveau compte
    assert elapsed < 0.05
