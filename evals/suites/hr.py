"""Suite HR : rejoue la présélection sur les trois offres du jeu doré.

Le pipeline exécuté ici est CELUI DE PRODUCTION, fonction par fonction
(`run_extraction`, `run_profile`, `run_scoring`, `finalize_run`) : mêmes
prompts versionnés, mêmes alias, même recalage sur la grille, même calcul de
note en code. La seule chose que le harnais remplace est l'enveloppe Celery,
qui n'apporte ici que de l'asynchronisme : la concurrence est bornée par
`--concurrence` plutôt que par le nombre de workers, et le limiteur de débit
Redis (`acquire_slot`, bloquant par conception) est laissé de côté parce qu'il
protège le fournisseur, il ne change pas ce qui est mesuré.

Ce qui est mesuré, offre par offre puis toutes offres confondues :
corrélation de Spearman entre la note de l'IA et la note de référence,
précision top-10 et top-20, exactitude sur les critères éliminatoires, taux
d'échec, temps et coût par CV, et la matrice de confusion par strate.
"""

from __future__ import annotations

import asyncio
import csv
import time
import uuid
from pathlib import Path
from typing import Any

from app.core.llm import LLMGateway
from app.core.tenant import tenant_session
from app.hr import pipeline
from app.hr.criteria import Criteria
from app.hr.models import (
    JOB_READY,
    RUN_RUNNING,
    Candidate,
    Job,
    ScreeningRun,
)
from app.hr.storage import FileStore
from evals import metriques
from evals.harnais import ORG_EVAL, USER_EVAL, dossier_donnees

STRATES = ("excellent", "bon", "limite", "hors_profil")


def offres_disponibles() -> list[str]:
    racine = dossier_donnees("hr")
    return sorted(p.name for p in racine.iterdir() if p.is_dir())


def lire_labels(chemin: Path) -> dict[str, dict[str, Any]]:
    """labels.csv -> {nom de fichier: {strate, score_ref, must_have_ok}}.

    Les labels sont lus, jamais réécrits : le harnais n'a aucun droit sur la
    référence (section NE PAS de la carte).
    """
    with chemin.open(encoding="utf-8", newline="") as flux:
        return {
            ligne["candidate_file"]: {
                "strate": ligne["strate"],
                "score_ref": float(ligne["score_ref_0_100"]),
                "must_have_ok": ligne["must_have_ok"].strip().lower() == "oui",
            }
            for ligne in csv.DictReader(flux)
        }


async def creer_campagne(
    offre: str, grille: Criteria, texte_offre: str, fichiers: list[Path], store: FileStore
) -> tuple[uuid.UUID, dict[uuid.UUID, str]]:
    """Offre, candidatures et campagne dans la base, comme le ferait l'écran RH.

    Renvoie l'identifiant de campagne et la table candidature -> nom de fichier
    d'origine, seule clé qui relie un résultat à son label.
    """
    async with tenant_session(ORG_EVAL, USER_EVAL) as session:
        job = Job(
            organization_id=ORG_EVAL,
            title=f"[eval] {offre}",
            description_text=texte_offre,
            criteria_json=grille.model_dump(mode="json"),
            criteria_prompt_version=None,
            status=JOB_READY,
            created_by=USER_EVAL,
        )
        session.add(job)
        await session.flush()
        job_id = job.id

        noms: dict[uuid.UUID, str] = {}
        for fichier in fichiers:
            donnees = fichier.read_bytes()
            kind = "pdf" if fichier.suffix.lower() == ".pdf" else "docx"
            chemin = store.save(org_id=ORG_EVAL, job_id=job_id, data=donnees, kind=kind)
            candidate = Candidate(
                organization_id=ORG_EVAL,
                job_id=job_id,
                file_path=chemin,
                original_filename=fichier.name,
                mime="application/pdf" if kind == "pdf" else "application/vnd.openxmlformats",
                size_bytes=len(donnees),
            )
            session.add(candidate)
            await session.flush()
            noms[candidate.id] = fichier.name

        run = ScreeningRun(organization_id=ORG_EVAL, job_id=job_id, status=RUN_RUNNING)
        session.add(run)
        await session.flush()
        return run.id, noms


async def _traiter_un_cv(
    run_id: uuid.UUID,
    candidate_id: uuid.UUID,
    grille: Criteria,
    store: FileStore,
    gateway: LLMGateway,
    verrou: asyncio.Semaphore,
) -> dict[str, Any]:
    """Un CV de bout en bout, exactement dans l'ordre des tâches Celery."""
    async with verrou:
        debut = time.monotonic()
        try:
            texte = await pipeline.run_extraction(ORG_EVAL, run_id, candidate_id, store)
            if texte is None:
                await pipeline.mark_failed(
                    ORG_EVAL, run_id, candidate_id, "Texte du CV indisponible", "extract"
                )
                return {"candidate_id": candidate_id, "statut": "echec_extraction"}
            profil = await pipeline.run_profile(
                ORG_EVAL, run_id, candidate_id, texte, gateway=gateway
            )
            note = await pipeline.run_scoring(
                ORG_EVAL, run_id, candidate_id, texte, grille, profil, gateway=gateway
            )
        except Exception as exc:  # noqa: BLE001 - un CV ne doit pas couler le lot
            await pipeline.mark_failed(
                ORG_EVAL, run_id, candidate_id, f"{type(exc).__name__}: {exc}", "score"
            )
            return {
                "candidate_id": candidate_id,
                "statut": "echec_notation",
                "erreur": f"{type(exc).__name__}",
            }
        return {
            "candidate_id": candidate_id,
            "statut": "note",
            "overall": note["overall"],
            "must_have_failed": note["must_have_failed"],
            "secondes": round(time.monotonic() - debut, 2),
        }


def _mesures(
    resultats: list[dict[str, Any]], noms: dict[uuid.UUID, str], labels: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    """Toutes les métriques d'une offre, à partir des résultats et des labels."""
    notes_ia: dict[str, float] = {}
    notes_ref: dict[str, float] = {}
    must_ia: list[bool] = []
    must_ref: list[bool] = []
    couples: list[tuple[str, str]] = []
    durees: list[float] = []

    par_strate: dict[str, list[float]] = {s: [] for s in STRATES}
    for nom, label in labels.items():
        if nom in {noms[r["candidate_id"]] for r in resultats}:
            par_strate[label["strate"]].append(label["score_ref"])
    bornes = metriques.bornes_de_strate({k: v for k, v in par_strate.items() if v})

    for resultat in resultats:
        nom = noms[resultat["candidate_id"]]
        attendu = labels.get(nom)
        if attendu is None or resultat["statut"] != "note":
            continue
        notes_ia[nom] = float(resultat["overall"])
        notes_ref[nom] = attendu["score_ref"]
        ok_ia = not resultat["must_have_failed"]
        must_ia.append(ok_ia)
        must_ref.append(bool(attendu["must_have_ok"]))
        if len(bornes) >= 2:
            couples.append(
                (
                    attendu["strate"],
                    metriques.strate_predite(float(resultat["overall"]), ok_ia, bornes),
                )
            )
        if "secondes" in resultat:
            durees.append(float(resultat["secondes"]))

    communs = sorted(notes_ia)
    echecs = [r for r in resultats if r["statut"] != "note"]
    return {
        "candidats": len(resultats),
        "notes": len(notes_ia),
        "echecs": len(echecs),
        "taux_echec": round(len(echecs) / len(resultats), 4) if resultats else 0.0,
        "spearman": metriques.spearman(
            [notes_ia[n] for n in communs], [notes_ref[n] for n in communs]
        ),
        "precision_top_10": metriques.precision_top_k(notes_ia, notes_ref, 10),
        "precision_top_20": metriques.precision_top_k(notes_ia, notes_ref, 20),
        "must_have": metriques.exactitude(must_ref, must_ia),
        "ecart_absolu_moyen": metriques.moyenne([abs(notes_ia[n] - notes_ref[n]) for n in communs]),
        "secondes_par_cv": metriques.moyenne(durees),
        "bornes_de_strate": {k: round(v, 1) for k, v in bornes.items()},
        # Les frontières viennent des scores de référence PRÉSENTS. Sur une
        # exécution partielle, une seule strate peut être représentée : il n'y
        # a alors aucune frontière à déduire, et une matrice de confusion
        # calculée quand même rangerait tout le monde dans la même case.
        "confusion": metriques.matrice_de_confusion(couples, STRATES) if couples else None,
        "detail": [
            {
                "fichier": n,
                "score_ia": notes_ia[n],
                "score_ref": notes_ref[n],
                "strate": labels[n]["strate"],
            }
            for n in communs
        ],
        "echecs_detail": [
            {"fichier": noms[r["candidate_id"]], "statut": r["statut"], "erreur": r.get("erreur")}
            for r in echecs
        ],
    }


async def executer(
    gateway: LLMGateway,
    limite: int | None = None,
    concurrence: int = 6,
    offres: list[str] | None = None,
) -> dict[str, Any]:
    """Rejoue la présélection sur chaque offre et renvoie le bloc de rapport.

    `limite` s'applique PAR OFFRE et prend les CV dans l'ordre alphabétique :
    un sous-ensemble tiré au hasard rendrait deux rapports incomparables. Un
    rapport produit avec une limite le dit, pour qu'aucun tableau du mémoire ne
    s'appuie dessus en le croyant complet.
    """
    store = FileStore()
    verrou = asyncio.Semaphore(concurrence)
    par_offre: dict[str, Any] = {}
    debut_total = time.monotonic()

    for offre in offres or offres_disponibles():
        racine = dossier_donnees("hr", offre)
        grille = Criteria.model_validate_json((racine / "grille.json").read_text(encoding="utf-8"))
        texte_offre = (racine / "offre.md").read_text(encoding="utf-8")
        labels = lire_labels(racine / "labels.csv")
        fichiers = sorted((racine / "cv").iterdir())
        if limite is not None:
            fichiers = fichiers[:limite]

        run_id, noms = await creer_campagne(offre, grille, texte_offre, fichiers, store)
        resultats = await asyncio.gather(
            *(
                _traiter_un_cv(run_id, candidate_id, grille, store, gateway, verrou)
                for candidate_id in noms
            )
        )
        await pipeline.finalize_run(ORG_EVAL, run_id)
        stats = await _stats_de_campagne(run_id)

        mesures = _mesures(list(resultats), noms, labels)
        mesures["run_id"] = str(run_id)
        mesures["cout_usd"] = stats.get("llm", {}).get("cost_usd")
        mesures["appels_llm"] = stats.get("llm", {}).get("calls")
        mesures["jetons"] = stats.get("llm", {}).get("tokens")
        notes = mesures["notes"] or 1
        mesures["cout_par_cv_usd"] = round((mesures["cout_usd"] or 0) / notes, 6)
        mesures["etapes"] = stats.get("steps")
        par_offre[offre] = mesures

    return {
        "offres": par_offre,
        "global": _agreger(par_offre),
        "secondes_total": round(time.monotonic() - debut_total, 1),
        "limite_par_offre": limite,
    }


async def _stats_de_campagne(run_id: uuid.UUID) -> dict[str, Any]:
    async with tenant_session(ORG_EVAL) as session:
        run = await session.get(ScreeningRun, run_id)
        return dict(run.stats_json or {}) if run is not None else {}


def _agreger(par_offre: dict[str, Any]) -> dict[str, Any]:
    """Chiffres toutes offres confondues.

    La corrélation globale est recalculée sur l'ensemble des points, jamais
    moyennée entre offres : une moyenne de corrélations ne veut rien dire.
    """
    details = [d for offre in par_offre.values() for d in offre["detail"]]
    ia = [d["score_ia"] for d in details]
    ref = [d["score_ref"] for d in details]
    couples = [
        (attendu, predit)
        for offre in par_offre.values()
        if offre["confusion"] is not None
        for attendu, ligne in offre["confusion"].items()
        for predit, nombre in ligne.items()
        for _ in range(nombre)
    ]
    must = [offre["must_have"] for offre in par_offre.values()]
    total_must = sum(int(m["total"]) for m in must)
    justes = sum(int(m["vrais_positifs"]) + int(m["vrais_negatifs"]) for m in must)
    couts = [o["cout_usd"] for o in par_offre.values() if o.get("cout_usd") is not None]
    durees = [o["secondes_par_cv"] for o in par_offre.values() if o.get("secondes_par_cv")]
    return {
        "candidats": sum(o["candidats"] for o in par_offre.values()),
        "notes": len(details),
        "echecs": sum(o["echecs"] for o in par_offre.values()),
        "taux_echec": round(
            sum(o["echecs"] for o in par_offre.values())
            / max(1, sum(o["candidats"] for o in par_offre.values())),
            4,
        ),
        "spearman": metriques.spearman(ia, ref),
        "exactitude_must_have": round(justes / total_must, 4) if total_must else None,
        "ecart_absolu_moyen": metriques.moyenne([abs(a - b) for a, b in zip(ia, ref, strict=True)]),
        "secondes_par_cv": metriques.moyenne(durees),
        "cout_usd": round(sum(couts), 6) if couts else None,
        "cout_par_cv_usd": round(sum(couts) / len(details), 6) if couts and details else None,
        "confusion": metriques.matrice_de_confusion(couples, STRATES) if couples else None,
    }
