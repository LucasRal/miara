"""API des campagnes : lancement non bloquant, progression, classement.

L'API ne fait jamais l'analyse — elle publie des tâches. Les tests substituent
donc la publication et vérifient le contrat : ce qui part vers le worker, ce
que voit le recruteur pendant que ça tourne, et ce qu'il lit à la fin.
"""

import uuid
from collections.abc import Callable
from typing import Any

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.hr import runs as runs_module
from app.hr.models import Candidate, CandidateScore, Job, ScreeningRun
from tests.test_hr_pipeline import GRILLE

OFFRE = {
    "title": "Ingénieur logiciel",
    "description_text": "Conception et exploitation de services Python en production." * 2,
}


@pytest.fixture
def publications(monkeypatch: pytest.MonkeyPatch) -> list[tuple[Any, ...]]:
    """Capture ce que l'API envoie au worker, sans courtier de messages."""
    envois: list[tuple[Any, ...]] = []

    def _faux_dispatch(run_id: uuid.UUID, org_id: uuid.UUID, candidate_ids: list[uuid.UUID]) -> str:
        envois.append((run_id, org_id, list(candidate_ids)))
        return "task-id"

    monkeypatch.setattr(runs_module, "dispatch_run", _faux_dispatch)
    return envois


async def _offre_prete(
    admin_sessions: async_sessionmaker[AsyncSession], org_id: uuid.UUID, nb_cv: int = 3
) -> tuple[uuid.UUID, list[uuid.UUID]]:
    async with admin_sessions() as s, s.begin():
        job = Job(
            organization_id=org_id,
            title=OFFRE["title"],
            description_text=OFFRE["description_text"],
            criteria_json=GRILLE,
            status="ready",
        )
        s.add(job)
        await s.flush()
        ids = []
        for i in range(nb_cv):
            candidate = Candidate(
                organization_id=org_id,
                job_id=job.id,
                file_path=f"{org_id}/{job.id}/{uuid.uuid4()}.pdf",
                original_filename=f"cv-{i}.pdf",
                mime="application/pdf",
                size_bytes=900,
                status="uploaded",
            )
            s.add(candidate)
            ids.append(candidate)
        await s.flush()
        return job.id, [c.id for c in ids]


async def test_lancement_repond_immediatement_et_publie_le_lot(
    hr_client: tuple[httpx.AsyncClient, uuid.UUID],
    admin_sessions: async_sessionmaker[AsyncSession],
    publications: list[tuple[Any, ...]],
) -> None:
    """202 tout de suite : l'API ne bloque pas pendant l'analyse."""
    client, org_id = hr_client
    job_id, candidats = await _offre_prete(admin_sessions, org_id, nb_cv=5)

    r = await client.post(f"/api/v1/hr/jobs/{job_id}/runs")
    assert r.status_code == 202, r.text
    body = r.json()
    assert body["status"] == "running"
    assert body["candidates"] == 5

    assert len(publications) == 1
    run_id, org_publie, cv_publies = publications[0]
    assert str(run_id) == body["run_id"]
    assert org_publie == org_id  # l'org vient du contexte, jamais du client
    assert sorted(cv_publies) == sorted(candidats)


async def test_pas_d_analyse_sans_grille_validee(
    hr_client: tuple[httpx.AsyncClient, uuid.UUID],
    publications: list[tuple[Any, ...]],
) -> None:
    client, _ = hr_client
    job_id = (await client.post("/api/v1/hr/jobs", json=OFFRE)).json()["id"]
    r = await client.post(f"/api/v1/hr/jobs/{job_id}/runs")
    assert r.status_code == 409
    assert "validée" in r.json()["detail"]
    assert publications == []


async def test_pas_d_analyse_sans_candidature(
    hr_client: tuple[httpx.AsyncClient, uuid.UUID],
    admin_sessions: async_sessionmaker[AsyncSession],
    publications: list[tuple[Any, ...]],
) -> None:
    client, org_id = hr_client
    job_id, _ = await _offre_prete(admin_sessions, org_id, nb_cv=0)
    r = await client.post(f"/api/v1/hr/jobs/{job_id}/runs")
    assert r.status_code == 409
    assert publications == []


async def test_progression_visible_pendant_l_analyse(
    hr_client: tuple[httpx.AsyncClient, uuid.UUID],
    admin_sessions: async_sessionmaker[AsyncSession],
    publications: list[tuple[Any, ...]],
) -> None:
    """Le recruteur voit avancer le lot, CV par CV, sans attendre la fin."""
    client, org_id = hr_client
    job_id, candidats = await _offre_prete(admin_sessions, org_id, nb_cv=4)
    run_id = (await client.post(f"/api/v1/hr/jobs/{job_id}/runs")).json()["run_id"]

    depart = (await client.get(f"/api/v1/hr/runs/{run_id}")).json()
    assert depart["total"] == 4
    assert depart["done"] == 0
    assert depart["progress"] == 0.0
    assert {c["status"] for c in depart["candidates"]} == {"pending"}

    # Deux CV notés, un en échec : la progression suit.
    async with admin_sessions() as s, s.begin():
        for i, candidat in enumerate(candidats[:2]):
            s.add(
                CandidateScore(
                    organization_id=org_id,
                    run_id=uuid.UUID(run_id),
                    candidate_id=candidat,
                    score_json={"criteria": [], "confidence": 0.9},
                    overall=80 - i * 10,
                    status="scored",
                )
            )
        s.add(
            CandidateScore(
                organization_id=org_id,
                run_id=uuid.UUID(run_id),
                candidate_id=candidats[2],
                score_json=None,
                overall=None,
                status="failed",
                error="PDF illisible",
            )
        )

    milieu = (await client.get(f"/api/v1/hr/runs/{run_id}")).json()
    assert milieu["done"] == 3
    assert milieu["progress"] == 0.75
    etats = {c["status"] for c in milieu["candidates"]}
    assert etats == {"scored", "failed", "pending"}
    echec = next(c for c in milieu["candidates"] if c["status"] == "failed")
    assert echec["error"] == "PDF illisible"


async def test_classement_final_avec_preuves(
    hr_client: tuple[httpx.AsyncClient, uuid.UUID],
    admin_sessions: async_sessionmaker[AsyncSession],
    publications: list[tuple[Any, ...]],
) -> None:
    client, org_id = hr_client
    job_id, candidats = await _offre_prete(admin_sessions, org_id, nb_cv=3)
    run_id = (await client.post(f"/api/v1/hr/jobs/{job_id}/runs")).json()["run_id"]
    async with admin_sessions() as s, s.begin():
        for rang, (candidat, note) in enumerate(zip(candidats, [90, 70, 50], strict=True), start=1):
            s.add(
                CandidateScore(
                    organization_id=org_id,
                    run_id=uuid.UUID(run_id),
                    candidate_id=candidat,
                    score_json={
                        "criteria": [
                            {
                                "name": "Développement Python",
                                "weight": 5,
                                "score_0_5": 4,
                                "evidence": "« FastAPI en production »",
                                "missing": None,
                            }
                        ],
                        "must_have_failed": [],
                        "confidence": 0.8,
                    },
                    overall=note,
                    rank=rang,
                    status="scored",
                )
            )

    body = (await client.get(f"/api/v1/hr/runs/{run_id}/results")).json()
    classement = body["ranking"]
    assert [x["rank"] for x in classement] == [1, 2, 3]
    assert [x["overall"] for x in classement] == [90, 70, 50]
    assert classement[0]["original_filename"] == "cv-0.pdf"
    # Chaque note porte sa preuve citée : c'est ce qui rend la décision contestable.
    assert classement[0]["criteria"][0]["evidence"].startswith("«")
    # Le chemin de stockage ne sort jamais.
    assert "file_path" not in (await client.get(f"/api/v1/hr/runs/{run_id}/results")).text

    # Pagination serveur : la cible est 500 CV par lot, la page reste bornée
    # et le total dit combien de CV passent le filtre.
    page = (await client.get(f"/api/v1/hr/runs/{run_id}/results?limit=2")).json()
    assert [x["rank"] for x in page["ranking"]] == [1, 2] and page["total"] == 3
    suite = (await client.get(f"/api/v1/hr/runs/{run_id}/results?limit=2&offset=2")).json()
    assert [x["rank"] for x in suite["ranking"]] == [3]

    # Filtres appliqués côté serveur : un seuil qui ne porterait que sur la
    # page affichée donnerait un classement faux.
    filtre = (await client.get(f"/api/v1/hr/runs/{run_id}/results?min_score=70")).json()
    assert filtre["total"] == 2 and [x["overall"] for x in filtre["ranking"]] == [90, 70]
    recherche = (await client.get(f"/api/v1/hr/runs/{run_id}/results?q=cv-1")).json()
    assert [x["original_filename"] for x in recherche["ranking"]] == ["cv-1.pdf"]


async def test_campagne_d_une_autre_org_invisible(
    hr_client: tuple[httpx.AsyncClient, uuid.UUID],
    admin_sessions: async_sessionmaker[AsyncSession],
    make_client: Callable[[], httpx.AsyncClient],
    auth_cleanup: dict[str, list],
    publications: list[tuple[Any, ...]],
) -> None:
    client, org_id = hr_client
    job_id, _ = await _offre_prete(admin_sessions, org_id, nb_cv=2)
    run_id = (await client.post(f"/api/v1/hr/jobs/{job_id}/runs")).json()["run_id"]

    autre = make_client()
    email = f"rh-c-{uuid.uuid4().hex[:8]}@test.miara.dev"
    auth_cleanup["emails"].append(email)
    await autre.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "correct-horse-42", "full_name": "Autre"},
    )
    r = await autre.post("/api/v1/orgs", json={"name": "Org C"})
    auth_cleanup["org_ids"].append(r.json()["id"])

    assert (await autre.get(f"/api/v1/hr/runs/{run_id}")).status_code == 404
    assert (await autre.get(f"/api/v1/hr/runs/{run_id}/results")).status_code == 404
    assert (await autre.post(f"/api/v1/hr/jobs/{job_id}/runs")).status_code == 404


async def test_campagne_inexistante(hr_client: tuple[httpx.AsyncClient, uuid.UUID]) -> None:
    client, _ = hr_client
    assert (await client.get(f"/api/v1/hr/runs/{uuid.uuid4()}")).status_code == 404


async def test_le_lot_publie_ignore_les_cv_deja_en_erreur(
    hr_client: tuple[httpx.AsyncClient, uuid.UUID],
    admin_sessions: async_sessionmaker[AsyncSession],
    publications: list[tuple[Any, ...]],
) -> None:
    """Un fichier déjà reconnu illisible ne repart pas dans la file `heavy`."""
    client, org_id = hr_client
    job_id, candidats = await _offre_prete(admin_sessions, org_id, nb_cv=3)
    async with admin_sessions() as s, s.begin():
        candidate = await s.get(Candidate, candidats[0])
        assert candidate is not None
        candidate.status = "error"

    body = (await client.post(f"/api/v1/hr/jobs/{job_id}/runs")).json()
    assert body["candidates"] == 2
    assert candidats[0] not in publications[0][2]


async def test_role_commercial_refuse(
    hr_client: tuple[httpx.AsyncClient, uuid.UUID],
    admin_sessions: async_sessionmaker[AsyncSession],
) -> None:
    from sqlalchemy import select, update

    from app.auth.models import Membership, MembershipRole

    client, org_id = hr_client
    async with admin_sessions() as s, s.begin():
        user_id = (
            await s.execute(select(Membership.user_id).where(Membership.organization_id == org_id))
        ).scalar_one()
        await s.execute(
            update(Membership)
            .where(Membership.organization_id == org_id, Membership.user_id == user_id)
            .values(role=MembershipRole.sales)
        )
    assert (await client.get(f"/api/v1/hr/runs/{uuid.uuid4()}")).status_code == 403


async def test_run_persiste_en_base(
    hr_client: tuple[httpx.AsyncClient, uuid.UUID],
    admin_sessions: async_sessionmaker[AsyncSession],
    publications: list[tuple[Any, ...]],
) -> None:
    """La campagne est en base AVANT que les tâches ne soient publiées."""
    client, org_id = hr_client
    job_id, _ = await _offre_prete(admin_sessions, org_id, nb_cv=2)
    run_id = (await client.post(f"/api/v1/hr/jobs/{job_id}/runs")).json()["run_id"]
    async with admin_sessions() as s:
        run = await s.get(ScreeningRun, uuid.UUID(run_id))
    assert run is not None
    assert run.status == "running"
    assert run.started_at is not None
    assert run.stats_json == {"candidates": 2}


# --- reprise d'un CV, suppression, campagnes d'une offre -------------------


@pytest.fixture
def reprises(monkeypatch: pytest.MonkeyPatch) -> list[tuple[Any, ...]]:
    """Capture les relances unitaires envoyées au worker."""
    envois: list[tuple[Any, ...]] = []

    def _faux_dispatch(run_id: uuid.UUID, org_id: uuid.UUID, candidate_id: uuid.UUID) -> str:
        envois.append((run_id, org_id, candidate_id))
        return "task-id"

    monkeypatch.setattr(runs_module, "dispatch_candidate", _faux_dispatch)
    return envois


async def test_campagnes_d_une_offre_listees_de_la_plus_recente(
    hr_client: tuple[httpx.AsyncClient, uuid.UUID],
    admin_sessions: async_sessionmaker[AsyncSession],
    publications: list[tuple[Any, ...]],
) -> None:
    client, org_id = hr_client
    job_id, _ = await _offre_prete(admin_sessions, org_id, nb_cv=2)
    premier = (await client.post(f"/api/v1/hr/jobs/{job_id}/runs")).json()["run_id"]
    second = (await client.post(f"/api/v1/hr/jobs/{job_id}/runs")).json()["run_id"]

    liste = (await client.get(f"/api/v1/hr/jobs/{job_id}/runs")).json()
    assert [r["run_id"] for r in liste] == [second, premier]

    # La liste des offres porte la dernière campagne, sans requête par ligne.
    offres = (await client.get("/api/v1/hr/jobs")).json()
    offre = next(o for o in offres if o["id"] == str(job_id))
    assert offre["last_run"]["run_id"] == second
    assert offre["candidates"] == 2


async def test_cv_en_echec_repris_sans_relancer_le_lot(
    hr_client: tuple[httpx.AsyncClient, uuid.UUID],
    admin_sessions: async_sessionmaker[AsyncSession],
    publications: list[tuple[Any, ...]],
    reprises: list[tuple[Any, ...]],
) -> None:
    """La reprise efface le résultat en échec et ne republie QUE ce CV."""
    client, org_id = hr_client
    job_id, candidats = await _offre_prete(admin_sessions, org_id, nb_cv=3)
    run_id = (await client.post(f"/api/v1/hr/jobs/{job_id}/runs")).json()["run_id"]
    async with admin_sessions() as s, s.begin():
        s.add(
            CandidateScore(
                organization_id=org_id,
                run_id=uuid.UUID(run_id),
                candidate_id=candidats[0],
                score_json=None,
                overall=None,
                status="failed",
                error="Quota fournisseur atteint",
            )
        )
        candidate = await s.get(Candidate, candidats[0])
        assert candidate is not None
        candidate.status = "error"

    r = await client.post(f"/api/v1/hr/runs/{run_id}/candidates/{candidats[0]}/retry")
    assert r.status_code == 202, r.text

    assert reprises == [(uuid.UUID(run_id), org_id, candidats[0])]
    assert publications and len(publications) == 1  # le lot n'est pas reparti

    # Le CV redevient « en attente » : la notation ne se croira pas déjà faite.
    suivi = (await client.get(f"/api/v1/hr/runs/{run_id}")).json()
    repris = next(c for c in suivi["candidates"] if c["candidate_id"] == str(candidats[0]))
    assert repris["status"] == "pending"
    assert repris["error"] is None
    assert repris["file_status"] == "uploaded"
    assert suivi["status"] == "running"
    assert suivi["done"] == 0


async def test_cv_deja_note_non_reprenable(
    hr_client: tuple[httpx.AsyncClient, uuid.UUID],
    admin_sessions: async_sessionmaker[AsyncSession],
    publications: list[tuple[Any, ...]],
    reprises: list[tuple[Any, ...]],
) -> None:
    """Rejouer un CV noté écraserait une évaluation : refusé."""
    client, org_id = hr_client
    job_id, candidats = await _offre_prete(admin_sessions, org_id, nb_cv=2)
    run_id = (await client.post(f"/api/v1/hr/jobs/{job_id}/runs")).json()["run_id"]
    async with admin_sessions() as s, s.begin():
        s.add(
            CandidateScore(
                organization_id=org_id,
                run_id=uuid.UUID(run_id),
                candidate_id=candidats[0],
                score_json={"criteria": [], "confidence": 0.7},
                overall=77,
                status="scored",
            )
        )

    r = await client.post(f"/api/v1/hr/runs/{run_id}/candidates/{candidats[0]}/retry")
    assert r.status_code == 409
    assert reprises == []

    autre = uuid.uuid4()
    assert (
        await client.post(f"/api/v1/hr/runs/{run_id}/candidates/{autre}/retry")
    ).status_code == 404


async def test_suppression_d_un_cv_efface_aussi_le_fichier(
    hr_client: tuple[httpx.AsyncClient, uuid.UUID],
    admin_sessions: async_sessionmaker[AsyncSession],
) -> None:
    """Donnée personnelle : retirer un CV de l'écran le retire du disque."""
    from app.hr.storage import get_file_store
    from app.main import app

    client, org_id = hr_client
    job_id = (await client.post("/api/v1/hr/jobs", json=OFFRE)).json()["id"]
    depot = await client.post(
        f"/api/v1/hr/jobs/{job_id}/candidates",
        files=[
            (
                "files",
                (
                    "cv.pdf",
                    b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\ntrailer\n%%EOF\n",
                    "application/pdf",
                ),
            )
        ],
    )
    assert depot.status_code == 201, depot.text
    candidate_id = depot.json()["accepted"][0]["id"]

    store = app.dependency_overrides[get_file_store]()
    async with admin_sessions() as s:
        candidate = await s.get(Candidate, uuid.UUID(candidate_id))
        assert candidate is not None
        chemin = store._resolve(candidate.file_path)
    assert chemin.exists()

    r = await client.delete(f"/api/v1/hr/jobs/{job_id}/candidates/{candidate_id}")
    assert r.status_code == 204
    assert not chemin.exists()
    assert (await client.get(f"/api/v1/hr/jobs/{job_id}/candidates")).json() == []
    assert (
        await client.delete(f"/api/v1/hr/jobs/{job_id}/candidates/{candidate_id}")
    ).status_code == 404


async def test_classement_porte_le_resume_du_profil(
    hr_client: tuple[httpx.AsyncClient, uuid.UUID],
    admin_sessions: async_sessionmaker[AsyncSession],
    publications: list[tuple[Any, ...]],
) -> None:
    """Chaque carte du classement affiche un résumé issu du CV, pas inventé."""
    client, org_id = hr_client
    job_id, candidats = await _offre_prete(admin_sessions, org_id, nb_cv=1)
    run_id = (await client.post(f"/api/v1/hr/jobs/{job_id}/runs")).json()["run_id"]
    async with admin_sessions() as s, s.begin():
        candidate = await s.get(Candidate, candidats[0])
        assert candidate is not None
        candidate.profile_json = {
            "headline": "Ingénieure backend Python",
            "years_experience": 7.5,
            "skills": [f"comp-{i}" for i in range(12)],
        }
        s.add(
            CandidateScore(
                organization_id=org_id,
                run_id=uuid.UUID(run_id),
                candidate_id=candidats[0],
                score_json={"criteria": [], "must_have_failed": [], "confidence": 0.9},
                overall=88,
                rank=1,
                status="scored",
            )
        )

    fiche = (await client.get(f"/api/v1/hr/runs/{run_id}/results")).json()["ranking"][0]
    assert fiche["headline"] == "Ingénieure backend Python"
    assert fiche["years_experience"] == 7.5
    assert len(fiche["skills"]) == 8  # le classement n'affiche pas douze compétences
