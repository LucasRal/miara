"""Écrans transverses : tableau de bord, file de traitement, usage.

Trois critères de la carte sont vérifiés ici : les totaux d'usage collent à
la somme brute de `llm_calls`, une tâche échouée apparaît dans la file avec
son motif et peut être relancée, et un commercial n'a pas accès à l'usage.
"""

import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import httpx
import pytest
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.auth.models import Membership, MembershipRole
from app.core.models import LLMCall, TaskEvent
from app.hr.models import Candidate, CandidateScore, Job, ScreeningRun
from app.sales.models import CrmWrite

PASSWORD = "correct-horse-42"


def _appel(org_id: uuid.UUID, agent: str, alias: str, cost: str, latence: int = 900) -> LLMCall:
    return LLMCall(
        organization_id=org_id,
        trace_id=uuid.uuid4(),
        agent=agent,
        alias=alias,
        model_used="mock",
        input_tokens=100,
        output_tokens=50,
        latency_ms=latence,
        cost_usd=Decimal(cost),
        status="ok",
    )


async def _client_owner(
    make_client: Callable[[], httpx.AsyncClient], auth_cleanup: dict[str, list], nom: str
) -> tuple[httpx.AsyncClient, uuid.UUID]:
    client = make_client()
    email = f"{nom}-{uuid.uuid4().hex[:8]}@test.miara.dev"
    auth_cleanup["emails"].append(email)
    r = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": PASSWORD, "full_name": "Propriétaire"},
    )
    assert r.status_code == 201
    r = await client.post("/api/v1/orgs", json={"name": f"Org {nom} {uuid.uuid4().hex[:5]}"})
    assert r.status_code == 201
    org_id = uuid.UUID(r.json()["id"])
    auth_cleanup["org_ids"].append(str(org_id))
    return client, org_id


# --- tableau de bord ------------------------------------------------------


async def test_tableau_de_bord_agrege_le_mois_et_liste_l_activite(
    make_client: Callable[[], httpx.AsyncClient],
    admin_sessions: async_sessionmaker[AsyncSession],
    auth_cleanup: dict[str, list],
) -> None:
    client, org_id = await _client_owner(make_client, auth_cleanup, "board")
    async with admin_sessions() as s, s.begin():
        job = Job(
            organization_id=org_id,
            title="Ingénieure logicielle",
            description_text="Poste de test pour le tableau de bord." * 2,
            status="ready",
        )
        s.add(job)
        await s.flush()
        run = ScreeningRun(
            organization_id=org_id,
            job_id=job.id,
            status="done",
            stats_json={"candidates": 3, "scored": 2, "failed": 1},
        )
        s.add(run)
        await s.flush()
        for i in range(3):
            candidate = Candidate(
                organization_id=org_id,
                job_id=job.id,
                file_path=f"{org_id}/{job.id}/{uuid.uuid4()}.pdf",
                original_filename=f"cv-{i}.pdf",
                mime="application/pdf",
                size_bytes=900,
                status="extracted",
            )
            s.add(candidate)
            await s.flush()
            s.add(
                CandidateScore(
                    organization_id=org_id,
                    run_id=run.id,
                    candidate_id=candidate.id,
                    score_json={"criteria": []},
                    overall=70,
                    status="scored" if i < 2 else "failed",
                )
            )
        s.add(
            CrmWrite(
                organization_id=org_id,
                trace_id=uuid.uuid4(),
                tool="create_task",
                sf_record_id="00T000000000001",
                status="created",
            )
        )
        s.add(_appel(org_id, "sales.assistant", "sales.synthesize", "0.010000", latence=1200))
        s.add(_appel(org_id, "sales.coach", "sales.synthesize", "0.020000", latence=800))
        # La notation d'un CV n'attend personne : elle ne doit pas entrer dans
        # la latence « ressentie » affichée sur le tableau de bord.
        s.add(_appel(org_id, "hr.score", "hr.score", "0.030000", latence=60000))

    r = await client.get("/api/v1/dashboard/summary")
    assert r.status_code == 200, r.text
    body = r.json()
    metrics = body["metrics"]
    assert metrics["cv_analyses"] == 2  # seuls les CV réellement notés
    assert metrics["ecritures_crm"] == 1
    assert metrics["latence_moyenne_ms"] == 1000  # moyenne de 1200 et 800
    assert metrics["heures_economisees"] == round(2 * metrics["minutes_par_cv"] / 60, 1)
    assert body["cv_total"] == 3
    kinds = [e["kind"] for e in body["activity"]]
    assert "hr_run" in kinds and "crm_write" in kinds
    run_event = next(e for e in body["activity"] if e["kind"] == "hr_run")
    # Les nombres partent bruts : l'accord et la mise en forme reviennent à
    # l'interface (« 1 noté » au singulier), pas au backend.
    assert run_event["counts"] == {"candidates": 3, "scored": 2, "failed": 1}
    ecriture = next(e for e in body["activity"] if e["kind"] == "crm_write")
    # Nom d'outil brut, jamais une phrase : l'interface a la table de libellés.
    assert ecriture["tool"] and "label" not in ecriture
    assert run_event["href"].startswith(f"/hr/{job.id}/runs/")


async def test_tableau_de_bord_sert_le_cache_au_second_appel(
    make_client: Callable[[], httpx.AsyncClient],
    auth_cleanup: dict[str, list],
) -> None:
    """Le cache évite de rejouer les agrégations à chaque affichage."""
    client, _ = await _client_owner(make_client, auth_cleanup, "cache")
    premier = await client.get("/api/v1/dashboard/summary")
    second = await client.get("/api/v1/dashboard/summary")
    assert premier.json()["cached"] is False
    assert second.json()["cached"] is True
    assert second.json()["generated_at"] == premier.json()["generated_at"]


async def test_activite_complete_paginee_et_filtrable(
    make_client: Callable[[], httpx.AsyncClient],
    admin_sessions: async_sessionmaker[AsyncSession],
    auth_cleanup: dict[str, list],
) -> None:
    """Le tableau de bord montre dix événements ; la vue complète les montre tous.

    L'aperçu du tableau de bord coupait à dix sans rien pour aller plus loin :
    au-delà, l'activité de l'organisation était simplement invisible.
    """
    client, org_id = await _client_owner(make_client, auth_cleanup, "activite")
    async with admin_sessions() as s, s.begin():
        for i in range(14):
            s.add(
                CrmWrite(
                    organization_id=org_id,
                    trace_id=uuid.uuid4(),
                    tool="create_task",
                    sf_record_id=f"00T00000000{i:04d}",
                    status="created",
                    created_at=datetime.now(UTC) - timedelta(minutes=i),
                )
            )
        job = Job(
            organization_id=org_id,
            title="Offre pour l'activité",
            description_text="Poste de test pour la vue d'activité complète." * 2,
            status="ready",
        )
        s.add(job)
        await s.flush()
        s.add(
            ScreeningRun(
                organization_id=org_id,
                job_id=job.id,
                status="done",
                stats_json={"candidates": 1, "scored": 1, "failed": 0},
                created_at=datetime.now(UTC) - timedelta(minutes=30),
            )
        )

    apercu = (await client.get("/api/v1/dashboard/summary")).json()["activity"]
    assert len(apercu) == 10, "l'aperçu reste un aperçu"

    page1 = (await client.get("/api/v1/dashboard/activity?limit=10&offset=0")).json()
    page2 = (await client.get("/api/v1/dashboard/activity?limit=10&offset=10")).json()
    assert page1["total"] == 15 and page2["total"] == 15
    assert len(page1["events"]) == 10 and len(page2["events"]) == 5

    # Aucun événement ne se répète d'une page à l'autre, et l'ordre est
    # continu : c'est ce qu'une pagination sur trois sources triées en
    # mémoire peut rater.
    dates = [e["at"] for e in page1["events"] + page2["events"]]
    assert dates == sorted(dates, reverse=True)
    assert len(set(dates)) == 15
    assert page1["events"][:10] == apercu

    # Le filtre par source porte sur le total, pas seulement sur la page.
    campagnes = (await client.get("/api/v1/dashboard/activity?kind=hr_run")).json()
    assert campagnes["total"] == 1 and [e["kind"] for e in campagnes["events"]] == ["hr_run"]
    assert (await client.get("/api/v1/dashboard/activity?kind=inconnu")).status_code == 422

    # Au-delà de la borne, on le dit au lieu de renvoyer une page trouée.
    assert (await client.get("/api/v1/dashboard/activity?offset=100&limit=25")).status_code == 422


# --- file de traitement ---------------------------------------------------


def _tache(org_id: uuid.UUID, nom: str, statut: str, erreur: str | None = None) -> TaskEvent:
    return TaskEvent(
        organization_id=org_id,
        task_id=uuid.uuid4().hex,
        name=nom,
        queue="heavy",
        status=statut,
        args_json=["run-1", "cv-1", str(org_id)],
        started_at=datetime.now(UTC) - timedelta(minutes=2),
        finished_at=datetime.now(UTC),
        duration_ms=4200,
        error=erreur,
    )


async def test_file_montre_les_echecs_et_les_filtre(
    make_client: Callable[[], httpx.AsyncClient],
    admin_sessions: async_sessionmaker[AsyncSession],
    auth_cleanup: dict[str, list],
) -> None:
    client, org_id = await _client_owner(make_client, auth_cleanup, "file")
    async with admin_sessions() as s, s.begin():
        s.add(_tache(org_id, "hr.score_candidate", "succeeded"))
        s.add(_tache(org_id, "hr.extract_text", "failed", "ValueError: PDF illisible"))

    toutes = (await client.get("/api/v1/queue/tasks")).json()
    assert len(toutes["tasks"]) == 2
    assert toutes["total"] == 2
    echecs = (await client.get("/api/v1/queue/tasks?status=failed")).json()
    assert echecs["total"] == 1
    assert echecs["tasks"][0]["error"] == "ValueError: PDF illisible"
    # Le motif lisible accompagne la trace technique, il ne la remplace pas.
    assert echecs["tasks"][0]["reason"]
    assert "ValueError" not in echecs["tasks"][0]["reason"]
    assert echecs["tasks"][0]["duration_ms"] == 4200
    # Pagination serveur : une page de 1 sur un total de 2.
    page = (await client.get("/api/v1/queue/tasks?limit=1&offset=1")).json()
    assert len(page["tasks"]) == 1 and page["total"] == 2
    assert (await client.get("/api/v1/queue/tasks?status=inconnu")).status_code == 422


async def test_relance_d_une_tache_echouee(
    make_client: Callable[[], httpx.AsyncClient],
    admin_sessions: async_sessionmaker[AsyncSession],
    auth_cleanup: dict[str, list],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """La relance republie la MÊME tâche avec ses arguments d'origine."""
    from app import queue as queue_module

    envois: list[tuple[str, Any, str]] = []

    class _Resultat:
        id = "nouvelle-tache"

    def _faux_send(nom: str, args: Any = None, queue: str = "light", **_: Any) -> _Resultat:
        envois.append((nom, args, queue))
        return _Resultat()

    monkeypatch.setattr(queue_module.celery_app, "send_task", _faux_send)

    client, org_id = await _client_owner(make_client, auth_cleanup, "relance")
    async with admin_sessions() as s, s.begin():
        echec = _tache(org_id, "hr.extract_text", "failed", "OSError: disque")
        s.add(echec)
        await s.flush()
        task_id = echec.task_id
        reussie = _tache(org_id, "hr.score_candidate", "succeeded")
        s.add(reussie)
        await s.flush()
        task_ok = reussie.task_id

    r = await client.post(f"/api/v1/queue/tasks/{task_id}/retry")
    assert r.status_code == 202, r.text
    assert envois == [("hr.extract_text", ["run-1", "cv-1", str(org_id)], "heavy")]

    # La ligne d'origine garde son échec (elle raconte une exécution qui a eu
    # lieu) et compte la relance. La nouvelle exécution aura sa propre ligne,
    # ouverte par les signaux du worker.
    apres = (await client.get("/api/v1/queue/tasks?status=failed")).json()
    relancee = next(t for t in apres["tasks"] if t["task_id"] == task_id)
    assert relancee["retried"] == 1
    assert relancee["error"] == "OSError: disque"

    # Une tâche réussie ne se rejoue pas : elle a pu écrire dans le CRM.
    assert (await client.post(f"/api/v1/queue/tasks/{task_ok}/retry")).status_code == 409
    assert (await client.post(f"/api/v1/queue/tasks/{uuid.uuid4().hex}/retry")).status_code == 404
    assert len(envois) == 1


async def test_relance_refusee_a_un_commercial(
    make_client: Callable[[], httpx.AsyncClient],
    admin_sessions: async_sessionmaker[AsyncSession],
    auth_cleanup: dict[str, list],
) -> None:
    client, org_id = await _client_owner(make_client, auth_cleanup, "role")
    async with admin_sessions() as s, s.begin():
        echec = _tache(org_id, "hr.extract_text", "failed", "OSError: disque")
        s.add(echec)
        await s.flush()
        task_id = echec.task_id
        await s.execute(
            update(Membership)
            .where(Membership.organization_id == org_id)
            .values(role=MembershipRole.sales)
        )

    # Le commercial voit la file (elle informe) mais ne relance pas (ça coûte).
    assert (await client.get("/api/v1/queue/tasks")).status_code == 200
    assert (await client.post(f"/api/v1/queue/tasks/{task_id}/retry")).status_code == 403


# --- usage ----------------------------------------------------------------


async def test_usage_coherent_avec_la_somme_brute(
    make_client: Callable[[], httpx.AsyncClient],
    admin_sessions: async_sessionmaker[AsyncSession],
    auth_cleanup: dict[str, list],
) -> None:
    """Critère de la carte : les totaux collent à SUM(cost_usd) de l'org."""
    client, org_id = await _client_owner(make_client, auth_cleanup, "usage")
    async with admin_sessions() as s, s.begin():
        s.add(_appel(org_id, "hr.score", "hr.score", "0.012500"))
        s.add(_appel(org_id, "hr.extract", "hr.extract", "0.000750"))
        s.add(_appel(org_id, "sales.assistant", "sales.synthesize", "0.030000"))

    async with admin_sessions() as s:
        attendu = (
            await s.execute(
                select(func.coalesce(func.sum(LLMCall.cost_usd), Decimal(0))).where(
                    LLMCall.organization_id == org_id
                )
            )
        ).scalar_one()

    total = (await client.get("/api/v1/usage")).json()
    assert total["cost_usd"] == float(attendu)

    jours = (await client.get("/api/v1/usage/daily?days=7")).json()
    assert round(sum(j["cost_usd"] for j in jours["series"]), 6) == float(attendu)
    assert jours["series"][-1]["day"] == datetime.now(UTC).date().isoformat()

    agents = (await client.get("/api/v1/usage/by-agent")).json()
    assert round(sum(a["cost_usd"] for a in agents["by_agent"]), 6) == float(attendu)
    assert {a["agent"] for a in agents["by_agent"]} == {"hr.score", "hr.extract", "sales.assistant"}

    appels = (await client.get("/api/v1/usage/calls?limit=50")).json()["calls"]
    assert len(appels) == 3
    # Le contenu des prompts n'apparaît nulle part (carte, section NE PAS).
    assert all("prompt" not in cle or cle == "prompt_version" for a in appels for cle in a)


async def test_usage_ferme_a_un_commercial(
    make_client: Callable[[], httpx.AsyncClient],
    admin_sessions: async_sessionmaker[AsyncSession],
    auth_cleanup: dict[str, list],
) -> None:
    """Critère de la carte : un `sales` ne peut pas ouvrir Usage."""
    client, org_id = await _client_owner(make_client, auth_cleanup, "usagesales")
    async with admin_sessions() as s, s.begin():
        await s.execute(
            update(Membership)
            .where(Membership.organization_id == org_id)
            .values(role=MembershipRole.sales)
        )
    for chemin in ("/usage", "/usage/daily", "/usage/by-agent", "/usage/calls"):
        assert (await client.get(f"/api/v1{chemin}")).status_code == 403, chemin


# --- espaces de travail ---------------------------------------------------


async def test_espace_filtre_activite_file_et_usage(
    make_client: Callable[[], httpx.AsyncClient],
    admin_sessions: async_sessionmaker[AsyncSession],
    auth_cleanup: dict[str, list],
) -> None:
    """L'espace actif restreint les trois écrans transverses, côté serveur.

    Filtrer la page déjà rendue ne suffirait pas : ces écrans sont paginés par
    le backend, et le total afficherait « 15 événements » en n'en montrant
    que trois. Le filtre porte donc sur le total autant que sur la page.
    """
    client, org_id = await _client_owner(make_client, auth_cleanup, "espace")
    async with admin_sessions() as s, s.begin():
        job = Job(
            organization_id=org_id,
            title="Offre pour les espaces",
            description_text="Poste de test pour la séparation des espaces." * 2,
            status="ready",
        )
        s.add(job)
        await s.flush()
        s.add(
            ScreeningRun(
                organization_id=org_id,
                job_id=job.id,
                status="done",
                stats_json={"candidates": 1, "scored": 1, "failed": 0},
            )
        )
        s.add(
            CrmWrite(
                organization_id=org_id,
                trace_id=uuid.uuid4(),
                tool="create_task",
                sf_record_id="00T000000000042",
                status="created",
            )
        )
        s.add(_tache(org_id, "hr.rank_run", "succeeded"))
        s.add(_tache(org_id, "sales.sync_crm", "succeeded"))
        s.add(_tache(org_id, "core.ping", "succeeded"))
        s.add(_appel(org_id, "hr.score", "hr.score", "0.030000"))
        s.add(_appel(org_id, "sales.assistant", "sales.synthesize", "0.010000"))
        s.add(_appel(org_id, "core.echo", "sales.route", "0.001000"))

    # Activité : l'espace RH ne connaît que les présélections, l'espace
    # commercial les écritures CRM et les analyses du coach.
    rh = (await client.get("/api/v1/dashboard/activity?espace=rh")).json()
    assert rh["total"] == 1
    assert {e["kind"] for e in rh["events"]} == {"hr_run"}
    assert rh["kinds"] == ["hr_run"]
    commercial = (await client.get("/api/v1/dashboard/activity?espace=commercial")).json()
    assert {e["kind"] for e in commercial["events"]} == {"crm_write"}
    assert commercial["kinds"] == ["coaching", "crm_write"]
    # Sans espace, on voit les deux : le filtre est débrayable.
    assert (await client.get("/api/v1/dashboard/activity")).json()["total"] == 2

    # File de traitement : les noms suivent `module.fonction`. Les tâches
    # techniques n'appartiennent à aucun espace et ne sortent que sans filtre.
    noms = lambda corps: {t["name"] for t in corps["tasks"]}  # noqa: E731
    file_rh = (await client.get("/api/v1/queue/tasks?espace=rh")).json()
    assert noms(file_rh) == {"hr.rank_run"} and file_rh["total"] == 1
    file_com = (await client.get("/api/v1/queue/tasks?espace=commercial")).json()
    assert noms(file_com) == {"sales.sync_crm"}
    assert "core.ping" in noms((await client.get("/api/v1/queue/tasks")).json())

    # Usage : coût et appels suivent le même périmètre, pour que le total en
    # haut de page ne contredise pas les lignes du bas.
    usage_rh = (await client.get("/api/v1/usage?espace=rh")).json()
    assert usage_rh["total_calls"] == 1
    assert usage_rh["cost_usd"] == pytest.approx(0.03)
    appels_rh = (await client.get("/api/v1/usage/calls?espace=rh")).json()
    assert appels_rh["total"] == 1 and appels_rh["calls"][0]["agent"] == "hr.score"
    agents_com = (await client.get("/api/v1/usage/by-agent?espace=commercial")).json()
    assert {a["agent"] for a in agents_com["by_agent"]} == {"sales.assistant"}
    jours_com = (await client.get("/api/v1/usage/daily?espace=commercial")).json()
    assert sum(j["calls"] for j in jours_com["series"]) == 1
    assert (await client.get("/api/v1/usage/calls")).json()["total"] == 3

    # Un espace inconnu est refusé partout de la même façon.
    for url in (
        "/api/v1/dashboard/activity?espace=marketing",
        "/api/v1/queue/tasks?espace=marketing",
        "/api/v1/usage/calls?espace=marketing",
    ):
        assert (await client.get(url)).status_code == 422, url
