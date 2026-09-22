"""Tests de la carte [SALES] agent assistant commercial + ContextBuilder.

Trois niveaux : le ContextBuilder seul (déterminisme, priorité, budget), les
endpoints conversationnels (final / confirmation / trace) avec une passerelle
LLM scriptée, et le flux SSE. Le CRM est un FakeCRM peuplé ; la base et le RLS
sont réels.
"""

import json
import uuid
from collections.abc import Callable
from datetime import date, timedelta
from typing import Any

import httpx
import pytest
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.auth.models import Membership, MembershipRole
from app.sales.agents.assistant import sales_assistant
from app.sales.context_builder import RECENT_DAYS, build, count_tokens
from tests.conftest import ScriptedGateway, Step, tool_call

# --- ContextBuilder ------------------------------------------------------


def _big_context(n: int = 40) -> dict[str, Any]:
    """Contexte volumineux : de quoi dépasser n'importe quel petit budget."""
    today = date.today()
    return {
        "account": {
            "id": "001AAA",
            "name": "TechStart SAS",
            "industry": "Logiciel",
            "phone": "01 23 45 67 89",
            "website": "techstart.example",
        },
        "contacts": [
            {
                "id": f"003{i:03d}",
                "name": f"Contact {i}",
                "title": "Responsable achats",
                "email": f"c{i}@techstart.example",
                "phone": "01 00 00 00 00",
            }
            for i in range(n)
        ],
        "open_opportunities": [
            {
                "id": f"006{i:03d}",
                "name": f"Licences lot {i}",
                "stage": "Proposition",
                "amount": 48000.0 + i,
                "close_date": "2026-12-31",
            }
            for i in range(n)
        ],
        "recent_activities": [
            {
                "id": f"00T{i:03d}",
                "type": "Task" if i % 2 else "Event",
                "subject": f"Échange numéro {i} avec le client",
                "date": (today - timedelta(days=i * 3)).isoformat(),
                "status": "Completed",
            }
            for i in range(n)
        ],
        "open_cases": [
            {
                "id": f"500{i:03d}",
                "case_number": f"0000{i:04d}",
                "subject": f"Incident {i}",
                "status": "Nouveau",
                "priority": "Haute",
            }
            for i in range(n)
        ],
    }


def test_context_builder_est_deterministe() -> None:
    data = _big_context()
    today = date(2026, 9, 20)
    first = build(data, budget_tokens=1000, today=today)
    second = build(data, budget_tokens=1000, today=today)
    assert first == second


def test_context_builder_respecte_la_priorite_et_le_budget() -> None:
    """Critère : budget 1 000 jetons → des éléments sont écartés, et ce sont
    les moins prioritaires ; le texte reste exploitable."""
    built = build(_big_context(), budget_tokens=1000)

    assert built.tokens_used <= 1000
    assert count_tokens(built.text) == built.tokens_used
    assert built.items_dropped > 0
    assert "budget de contexte atteint" in built.text

    kept_opps, total_opps = built.sections["opportunites_ouvertes"]
    assert kept_opps > 0  # la priorité 1 passe toujours en premier
    # Les sections moins prioritaires sont servies après : aucune ne peut être
    # plus complète que la précédente une fois le budget saturé.
    order = ["opportunites_ouvertes", "activites_recentes", "contacts", "cas_ouverts"]
    ratios = [built.sections[k][0] / built.sections[k][1] for k in order]
    assert ratios == sorted(ratios, reverse=True)
    assert total_opps == 40

    # Le texte reste un briefing valide : en-tête intact et ids présents.
    assert built.text.startswith("COMPTE TechStart SAS (001AAA)")
    assert "006000" in built.text


def test_context_builder_budget_large_ne_perd_rien() -> None:
    built = build(_big_context(), budget_tokens=100_000)
    assert built.items_dropped == 0
    assert all(kept == total for kept, total in built.sections.values())
    # Les activités sont scindées sur la fenêtre « chaude ».
    assert built.sections["activites_recentes"][0] > 0
    assert built.sections["activites_anciennes"][0] > 0
    assert f"ACTIVITÉS DES {RECENT_DAYS} DERNIERS JOURS" in built.text


def test_context_builder_tolere_un_compte_vide() -> None:
    built = build({"account": {"id": "001ZZZ", "name": "Compte nu"}}, budget_tokens=3000)
    assert built.items_dropped == 0
    assert built.text == "COMPTE Compte nu (001ZZZ)"


async def _new_conversation(client: httpx.AsyncClient) -> str:
    r = await client.post("/api/v1/sales/conversations")
    assert r.status_code == 201
    return str(r.json()["id"])


# --- endpoints -----------------------------------------------------------


async def test_briefing_cite_les_ids_et_escalade_les_modeles(
    sales_client: tuple[httpx.AsyncClient, uuid.UUID, dict[str, str]],
    scripted: Callable[..., ScriptedGateway],
) -> None:
    """Un tour complet : recherche du compte, contexte, puis briefing. Le
    contexte rendu au modèle porte les ids ; l'escalade route → synthesize est
    décidée par le runtime."""
    client, _, ids = sales_client
    gateway = scripted(
        Step(tool_calls=[tool_call("c1", "find_account", name="TechStart")]),
        Step(tool_calls=[tool_call("c2", "get_account_context", account_id=ids["techstart"])]),
        Step(content=f"Opportunité en cours ({ids['opp_open']}) chez TechStart SAS."),
    )
    conversation_id = await _new_conversation(client)

    r = await client.post(
        f"/api/v1/sales/conversations/{conversation_id}/messages",
        json={"message": "Que dois-je savoir avant d'appeler Hanta chez TechStart ?"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["type"] == "final" and ids["opp_open"] in body["content"]

    # 1er appel sur l'alias léger, synthèses sur l'alias fort (ADR-011).
    assert gateway.aliases == ["sales.route", "sales.synthesize", "sales.synthesize"]
    # Le catalogue exposé au modèle = lectures + écritures, sans SOQL libre.
    assert gateway.tool_schemas is not None
    names = {t["function"]["name"] for t in gateway.tool_schemas}
    assert names == {t.name for t in sales_assistant.tools}
    assert not any("soql" in n or "query" in n for n in names)

    # La conversation rend ses messages ET sa trace.
    r = await client.get(f"/api/v1/sales/conversations/{conversation_id}")
    assert r.status_code == 200
    detail = r.json()
    assert [m["role"] for m in detail["messages"]] == [
        "user",
        "assistant",
        "tool",
        "assistant",
        "tool",
        "assistant",
    ]
    kinds = [t["kind"] for t in detail["trace"]]
    assert kinds.count("llm_call") == 3 and kinds.count("tool_exec") == 2
    assert kinds[-1] == "final"
    # Le contexte injecté au modèle est bien le texte compact sous budget.
    context_step = next(t for t in detail["trace"] if t["tool"] == "get_account_context")
    assert "COMPTE TechStart SAS" in (context_step["summary"] or "")


async def test_demande_d_action_renvoie_une_confirmation_lisible(
    sales_client: tuple[httpx.AsyncClient, uuid.UUID, dict[str, str]],
    scripted: Callable[..., ScriptedGateway],
) -> None:
    """Critère : une demande d'action s'arrête sur `needs_confirmation` avec un
    aperçu lisible, et rien n'est écrit tant que l'humain n'a pas confirmé."""
    from app.sales.crm.factory import _fakes

    client, org_id, ids = sales_client
    gateway = scripted(
        Step(
            tool_calls=[
                tool_call(
                    "w1",
                    "create_task",
                    subject="Relance TechStart",
                    due_date="2026-09-30",
                    related_record_id=ids["techstart"],
                )
            ]
        ),
        Step(content="C'est noté : la tâche de relance est créée."),
    )
    conversation_id = await _new_conversation(client)
    before = len(await _fakes[org_id].query("SELECT Id FROM Task"))

    r = await client.post(
        f"/api/v1/sales/conversations/{conversation_id}/messages",
        json={"message": "Crée-moi une tâche de relance pour TechStart le 30 septembre."},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["type"] == "needs_confirmation"
    assert body["tool"] == "create_task" and body["call_id"] == "w1"
    assert "Relance TechStart" in body["preview"] and "30/09/2026" in body["preview"]
    assert len(await _fakes[org_id].query("SELECT Id FROM Task")) == before

    # Confirmation : l'outil s'exécute, puis le modèle conclut.
    r = await client.post(f"/api/v1/sales/conversations/{conversation_id}/confirm/w1")
    assert r.status_code == 200
    assert r.json()["type"] == "final"
    after = await _fakes[org_id].query("SELECT Id, Subject FROM Task")
    assert len(after) - before == 1
    # La reprise après confirmation synthétise avec le modèle fort.
    assert gateway.aliases == ["sales.route", "sales.synthesize"]


async def test_confirmation_rejouee_n_ecrit_qu_une_fois(
    sales_client: tuple[httpx.AsyncClient, uuid.UUID, dict[str, str]],
    scripted: Callable[..., ScriptedGateway],
) -> None:
    """Double clic sur « Confirmer » : le trace_id de reprise est déterministe,
    donc la clé d'idempotence des écritures est la même."""
    from app.sales.crm.factory import _fakes

    client, org_id, ids = sales_client
    scripted(
        Step(
            tool_calls=[
                tool_call(
                    "w1",
                    "create_task",
                    subject="Relance",
                    due_date="2026-09-30",
                    related_record_id=ids["techstart"],
                )
            ]
        ),
        Step(content="Tâche créée."),
        Step(content="Tâche déjà créée."),
    )
    conversation_id = await _new_conversation(client)
    before = len(await _fakes[org_id].query("SELECT Id FROM Task"))
    await client.post(
        f"/api/v1/sales/conversations/{conversation_id}/messages",
        json={"message": "Crée une tâche de relance."},
    )
    await client.post(f"/api/v1/sales/conversations/{conversation_id}/confirm/w1")
    await client.post(f"/api/v1/sales/conversations/{conversation_id}/confirm/w1")
    assert len(await _fakes[org_id].query("SELECT Id FROM Task")) - before == 1


async def test_budget_reduit_ecarte_des_elements_et_repond_quand_meme(
    sales_client: tuple[httpx.AsyncClient, uuid.UUID, dict[str, str]],
    scripted: Callable[..., ScriptedGateway],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Critère : budget 1 000 jetons → `items_dropped` > 0 et réponse valide."""
    from app.sales.crm.factory import _fakes
    from app.sales.tools import read as read_module

    client, org_id, ids = sales_client
    # Un compte volumineux : 60 contacts en plus du jeu de démo.
    for i in range(60):
        await _fakes[org_id].create(
            "Contact",
            {
                "Name": f"Contact numéro {i}",
                "AccountId": ids["techstart"],
                "Email": f"contact{i}@techstart.example",
                "Title": "Responsable des achats indirects",
                "Phone": "01 02 03 04 05",
            },
        )
    monkeypatch.setattr(read_module.settings, "SALES_CONTEXT_BUDGET_TOKENS", 1000)

    scripted(
        Step(tool_calls=[tool_call("c1", "get_account_context", account_id=ids["techstart"])]),
        Step(content=f"Briefing partiel pour TechStart ({ids['techstart']})."),
    )
    conversation_id = await _new_conversation(client)
    r = await client.post(
        f"/api/v1/sales/conversations/{conversation_id}/messages",
        json={"message": "Prépare mon appel chez TechStart."},
    )
    assert r.status_code == 200
    assert r.json()["type"] == "final"

    detail = (await client.get(f"/api/v1/sales/conversations/{conversation_id}")).json()
    tool_msg = next(m for m in detail["messages"] if m["role"] == "tool")
    payload = json.loads(tool_msg["content"])
    assert payload["items_dropped"] > 0
    assert payload["tokens_used"] <= 1000
    # La réponse reste valide : en-tête et opportunité ouverte conservées.
    assert payload["context"].startswith("COMPTE TechStart SAS")
    assert ids["opp_open"] in payload["context"]


async def test_flux_sse_diffuse_les_etapes_puis_le_resultat(
    sales_client: tuple[httpx.AsyncClient, uuid.UUID, dict[str, str]],
    scripted: Callable[..., ScriptedGateway],
) -> None:
    client, _, ids = sales_client
    scripted(
        Step(tool_calls=[tool_call("c1", "find_account", name="TechStart")]),
        Step(content="TechStart SAS est bien dans votre portefeuille."),
    )
    conversation_id = await _new_conversation(client)

    chunks: list[str] = []
    async with client.stream(
        "POST",
        f"/api/v1/sales/conversations/{conversation_id}/messages/stream",
        json={"message": "TechStart est-il client ?"},
    ) as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        async for chunk in response.aiter_text():
            chunks.append(chunk)

    body = "".join(chunks)
    events = [line for line in body.splitlines() if line.startswith("event: ")]
    assert events.count("event: step") >= 3  # llm_call, tool_exec, llm_call, final
    assert events[-1] == "event: result"
    steps = [
        json.loads(line.removeprefix("data: "))
        for line in body.splitlines()
        if line.startswith("data: ")
    ]
    assert steps[0]["kind"] == "llm_call"
    assert any(s.get("tool") == "find_account" for s in steps)
    assert steps[-1]["type"] == "final"


async def test_role_rh_ne_peut_pas_parler_a_l_agent_commercial(
    sales_client: tuple[httpx.AsyncClient, uuid.UUID, dict[str, str]],
    admin_sessions: async_sessionmaker[AsyncSession],
) -> None:
    """Rôles autorisés : owner, admin, sales — le rôle est relu en base."""
    client, org_id, _ = sales_client
    async with admin_sessions() as s, s.begin():
        user_id = (
            await s.execute(select(Membership.user_id).where(Membership.organization_id == org_id))
        ).scalar_one()
        await s.execute(
            update(Membership)
            .where(Membership.organization_id == org_id, Membership.user_id == user_id)
            .values(role=MembershipRole.hr)
        )
    r = await client.post("/api/v1/sales/conversations")
    assert r.status_code == 403


async def test_conversation_d_une_autre_org_est_invisible(
    sales_client: tuple[httpx.AsyncClient, uuid.UUID, dict[str, str]],
    admin_sessions: async_sessionmaker[AsyncSession],
) -> None:
    client, _, _ = sales_client
    conversation_id = await _new_conversation(client)
    # Un id inexistant et un id d'une autre org donnent le même résultat : 404.
    assert (await client.get(f"/api/v1/sales/conversations/{uuid.uuid4()}")).status_code == 404
    assert (await client.get(f"/api/v1/sales/conversations/{conversation_id}")).status_code == 200


async def test_liste_des_conversations_titre_et_compte(
    sales_client: tuple[httpx.AsyncClient, uuid.UUID, dict[str, str]],
    scripted: Callable[..., ScriptedGateway],
) -> None:
    """Panneau de gauche de l'écran commercial : fils du commercial, titrés par
    leur première question, la plus récente d'abord."""
    client, _, _ = sales_client
    scripted(Step(content="Rien à signaler."))

    vide = await _new_conversation(client)
    parlante = await _new_conversation(client)
    r = await client.post(
        f"/api/v1/sales/conversations/{parlante}/messages",
        json={"message": "Prépare mon appel avec TechStart"},
    )
    assert r.status_code == 200

    r = await client.get("/api/v1/sales/conversations")
    assert r.status_code == 200
    fils = {c["id"]: c for c in r.json()}
    assert fils[str(parlante)]["title"] == "Prépare mon appel avec TechStart"
    assert fils[str(parlante)]["messages"] == 2
    # Un fil sans message garde un titre de repli, jamais « null ».
    assert fils[str(vide)]["title"] == "Nouvelle conversation"
    assert fils[str(vide)]["messages"] == 0
    # Ordre : le plus récent d'abord.
    assert [c["id"] for c in r.json()][0] == str(parlante)


async def test_action_refusee_puis_nouvelle_question(
    sales_client: tuple[httpx.AsyncClient, uuid.UUID, dict[str, str]],
    scripted: Callable[..., ScriptedGateway],
) -> None:
    """Refuser une action ne doit ni écrire, ni rejouer l'action, ni casser le fil.

    L'appel d'outil laissé sans résultat est clos comme « non confirmé » avant
    le tour suivant : sans cela l'historique devient invalide (un message
    assistant porteur de tool_calls suivi d'un message utilisateur) et l'action
    écartée serait exécutée à la question d'après.
    """
    from app.sales.crm.factory import _fakes

    client, org_id, ids = sales_client
    scripted(
        # Tour 1 : l'agent propose une écriture, l'humain refuse (aucun appel
        # de confirmation n'est fait, on enchaîne sur une autre question).
        Step(
            tool_calls=[
                tool_call(
                    "w1",
                    "create_task",
                    subject="Relance",
                    due_date="2026-10-01",
                    related_record_id=ids["techstart"],
                )
            ]
        ),
        # Tour 2 : nouvelle question, réponse directe.
        Step(content="Aucune tâche créée."),
    )
    conversation_id = await _new_conversation(client)

    r = await client.post(
        f"/api/v1/sales/conversations/{conversation_id}/messages",
        json={"message": "Crée une tâche de relance pour TechStart"},
    )
    assert r.json()["type"] == "needs_confirmation"
    avant = len(await _fakes[org_id].query("SELECT Id FROM Task"))

    r = await client.post(
        f"/api/v1/sales/conversations/{conversation_id}/messages",
        json={"message": "Finalement non. Quelles opportunités sont ouvertes ?"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["type"] == "final"
    # Rien d'écrit : l'action refusée n'est pas rejouée.
    assert len(await _fakes[org_id].query("SELECT Id FROM Task")) == avant

    # Le refus est tracé dans l'historique, en face de l'appel resté en attente.
    detail = (await client.get(f"/api/v1/sales/conversations/{conversation_id}")).json()
    refus = [m for m in detail["messages"] if m["role"] == "tool" and m["tool_call_id"] == "w1"]
    assert len(refus) == 1 and "non confirmée" in refus[0]["content"]
    # Ordre valide : chaque appel d'outil est suivi de son résultat.
    roles = [m["role"] for m in detail["messages"]]
    assert roles.index("tool") == roles.index("assistant") + 1


async def test_conversation_renommee_puis_supprimee(
    sales_client: tuple[httpx.AsyncClient, uuid.UUID, dict[str, str]],
) -> None:
    """Le titre vient de l'utilisateur ; la suppression emporte les messages."""
    client, _, _ = sales_client
    conversation_id = await _new_conversation(client)

    r = await client.patch(
        f"/api/v1/sales/conversations/{conversation_id}", json={"title": "Renouvellement Edge"}
    )
    assert r.status_code == 200 and r.json()["title"] == "Renouvellement Edge"
    liste = (await client.get("/api/v1/sales/conversations")).json()
    assert next(c for c in liste if c["id"] == conversation_id)["title"] == "Renouvellement Edge"

    assert (
        await client.delete(f"/api/v1/sales/conversations/{conversation_id}")
    ).status_code == 204
    assert conversation_id not in [
        c["id"] for c in (await client.get("/api/v1/sales/conversations")).json()
    ]
    # Un fil supprimé n'est plus lisible, et il l'est toujours pour le RLS.
    assert (await client.get(f"/api/v1/sales/conversations/{conversation_id}")).status_code == 404


async def test_suggestions_nomment_des_comptes_reels_de_l_org(
    sales_client: tuple[httpx.AsyncClient, uuid.UUID, dict[str, str]],
) -> None:
    """L'état vide ne propose jamais un compte absent du CRM de l'organisation."""
    client, org_id, _ = sales_client
    body = (await client.get("/api/v1/sales/suggestions")).json()
    assert body["connected"] is True
    assert 1 <= len(body["suggestions"]) <= 3
    assert all(s.endswith("?") for s in body["suggestions"])

    # Chaque suggestion qui nomme un compte nomme un compte QUI EXISTE dans le
    # CRM de cette organisation : c'est tout l'objet de la carte (une
    # suggestion codée en dur échouait au premier clic).
    from app.sales.crm import FakeCRM
    from app.sales.crm.factory import _fakes

    crm = _fakes[org_id]
    assert isinstance(crm, FakeCRM)
    reels = {
        str(ligne["Name"])
        for ligne in await crm.query("SELECT Id, Name FROM Account")
        if ligne.get("Name")
    }
    nommees = [s for s in body["suggestions"] if s.startswith("Que dois-je savoir")]
    assert nommees, "le jeu de démonstration a des opportunités ouvertes"
    for suggestion in nommees:
        compte = suggestion.removeprefix("Que dois-je savoir avant d'appeler ").removesuffix(" ?")
        assert compte in reels


async def test_recherche_de_comptes_par_nom(
    sales_client: tuple[httpx.AsyncClient, uuid.UUID, dict[str, str]],
) -> None:
    """Un compte se trouve par son nom — l'identifiant reste interne.

    L'écran du coach demandait un `001...` de dix-huit caractères tapé à la
    main. C'est cet endpoint qui le remplace : il rend le nom à montrer ET
    l'identifiant à envoyer, pour que la sélection reste un geste de
    l'utilisateur et non une résolution confiée au modèle.
    """
    client, org_id, _ = sales_client
    from app.sales.crm import FakeCRM
    from app.sales.crm.factory import _fakes

    crm = _fakes[org_id]
    assert isinstance(crm, FakeCRM)
    comptes = await crm.query("SELECT Id, Name FROM Account")
    cible = next(c for c in comptes if c.get("Name"))
    nom = str(cible["Name"])

    # Un fragment suffit, et la casse est indifférente : personne ne tape le
    # nom exact d'un compte.
    r = await client.get(f"/api/v1/sales/accounts?q={nom[:4].lower()}")
    assert r.status_code == 200
    trouves = r.json()
    assert str(cible["Id"]) in [c["id"] for c in trouves]
    assert all(set(c) == {"id", "name", "industry"} for c in trouves)
    assert len(trouves) <= 10

    # Sous deux caractères, on n'interroge pas le CRM : la frappe en cours
    # n'est pas une recherche.
    assert (await client.get("/api/v1/sales/accounts?q=a")).json() == []
    assert (await client.get("/api/v1/sales/accounts")).json() == []

    # L'apostrophe est un caractère de nom d'entreprise, pas une fin de
    # chaîne SOQL : elle est échappée, jamais renvoyée en erreur.
    r = await client.get("/api/v1/sales/accounts?q=l%27Or%C3%A9al%27")
    assert r.status_code == 200 and r.json() == []
