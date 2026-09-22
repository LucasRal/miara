"""Parties calculatoires de la campagne de charge (`evals/charge`).

Rien de ce qui touche au réseau, aux workers ou à la base n'est testé ici :
ce fichier vérifie ce qui décide des chiffres du chapitre 8 — le plafond de
budget, l'écart de reproductibilité, le verdict de la file `light`, la
composition du corpus et le plan de campagne.
"""

from pathlib import Path

import pytest

from evals.charge import campagne, mesures, scenarios
from evals.charge import worker as worker_charge

# --- budget ---------------------------------------------------------------


def test_budget_autorise_tant_que_l_estimation_tient() -> None:
    budget = mesures.Budget(plafond_usd=10.0)
    assert budget.autorise(10.0)
    assert not budget.autorise(10.01)


def test_budget_cumule_les_depenses_et_se_ferme() -> None:
    budget = mesures.Budget(plafond_usd=1.0)
    budget.ajouter(0.4)
    budget.ajouter(0.4)
    assert budget.depense_usd == pytest.approx(0.8)
    assert budget.reste_usd == pytest.approx(0.2)
    assert not budget.depasse
    assert not budget.autorise(0.3)
    budget.ajouter(0.25)
    assert budget.depasse


def test_budget_ne_regresse_pas_sous_zero() -> None:
    budget = mesures.Budget(plafond_usd=2.0, depense_usd=2.5)
    assert budget.depasse
    assert budget.reste_usd < 0


# --- débit et écarts ------------------------------------------------------


def test_debit_cv_par_minute() -> None:
    assert mesures.debit_cv_par_minute(50, 120) == 25.0
    assert mesures.debit_cv_par_minute(50, 0) is None


def test_ecart_relatif_est_l_etendue_sur_la_moyenne() -> None:
    assert mesures.ecart_relatif([10.0, 10.0, 10.0]) == 0.0
    # (11 - 9) / 10 = 0,2
    assert mesures.ecart_relatif([9.0, 10.0, 11.0]) == pytest.approx(0.2)
    assert mesures.ecart_relatif([5.0]) is None


def test_reproductibilite_tranche_au_seuil_de_dix_pour_cent() -> None:
    serre = mesures.reproductibilite("debit", "hr-50@c4", [20.0, 20.5, 21.0])
    assert serre.ecart_relatif == pytest.approx(0.0488, abs=1e-4)
    assert serre.tenu is True

    large = mesures.reproductibilite("debit", "hr-50@c8", [20.0, 25.0, 30.0])
    assert large.tenu is False
    assert large.en_dict()["tolerance"] == 0.10


def test_reproductibilite_sans_repetition_ne_tranche_pas() -> None:
    """Une seule mesure ne dit rien : `tenu` doit rester None, pas True."""
    assert mesures.reproductibilite("debit", "hr-500@c8", [12.0]).tenu is None


def test_points_aberrants_signale_sans_retirer() -> None:
    valeurs = [10.0, 10.1, 9.9, 10.05, 30.0]
    indices = mesures.points_aberrants(valeurs)
    assert indices == [4]
    # La moyenne publiée garde le point : la fonction signale, elle n'exclut pas.
    assert mesures.moyenne(valeurs) == pytest.approx(14.01)


def test_points_aberrants_sans_dispersion() -> None:
    assert mesures.points_aberrants([5.0, 5.0, 5.0]) == []


# --- critère de la file light --------------------------------------------


def test_verdict_file_light() -> None:
    assert mesures.verdict_file_light(4.0, 3.0)["tenu"] is True
    assert mesures.verdict_file_light(4.6, 3.0)["tenu"] is False
    assert mesures.verdict_file_light(4.0, 3.0)["rapport"] == pytest.approx(1.333, abs=1e-3)


def test_verdict_file_light_sans_reference_ne_declare_rien() -> None:
    assert mesures.verdict_file_light(4.0, None)["tenu"] is None
    assert mesures.verdict_file_light(None, 3.0)["tenu"] is None


def test_famine_light_une_sonde_perdue_suffit() -> None:
    """Un `core.ping` sans réponse est un verdict, pas une donnée manquante."""
    famine = mesures.famine_file_light(
        {"p95_secondes": 0.07, "sans_reponse": 0},
        {"p95_secondes": 25.37, "sans_reponse": 2},
    )
    assert famine["famine"] is True
    assert famine["sondes_sans_reponse"] == 2


def test_famine_light_file_fluide() -> None:
    famine = mesures.famine_file_light(
        {"p95_secondes": 0.05, "sans_reponse": 0},
        {"p95_secondes": 0.12, "sans_reponse": 0},
    )
    assert famine["famine"] is False
    assert famine["rapport"] == pytest.approx(2.4, abs=1e-3)


def test_famine_light_sans_mesure_ne_declare_rien() -> None:
    famine = mesures.famine_file_light(
        {"p95_secondes": None, "sans_reponse": 0},
        {"p95_secondes": None, "sans_reponse": 0},
    )
    assert famine["famine"] is None


# --- CSV ------------------------------------------------------------------


def test_ecrire_csv_ecrit_l_entete_meme_sans_ligne(tmp_path: Path) -> None:
    chemin = mesures.ecrire_csv(tmp_path / "vide.csv", [], ("a", "b"))
    assert chemin.read_text(encoding="utf-8").strip() == "a,b"


def test_ecrire_csv_ignore_les_colonnes_en_trop(tmp_path: Path) -> None:
    chemin = mesures.ecrire_csv(tmp_path / "x.csv", [{"a": 1, "z": 9}], ("a",))
    assert chemin.read_text(encoding="utf-8").splitlines() == ["a", "1"]


# --- corpus ---------------------------------------------------------------


def test_corpus_est_deterministe_et_se_repete() -> None:
    petit = scenarios.corpus(50, graine=7)
    assert len(petit) == 50
    assert len(set(petit)) == 50  # sous 180, aucun document n'est réemployé
    assert petit == scenarios.corpus(50, graine=7)
    assert petit != scenarios.corpus(50, graine=8)


def test_corpus_de_500_reemploie_le_jeu_dore() -> None:
    grand = scenarios.corpus(500, graine=7)
    assert len(grand) == 500
    distincts = len(set(grand))
    assert distincts == 180  # le jeu doré n'en contient pas davantage
    # Le préfixe de 180 est exactement le jeu doré mélangé une fois.
    assert grand[:180] == scenarios.corpus(180, graine=7)
    assert grand[180] == grand[0]


def test_repetition_du_corpus_dit_la_verite() -> None:
    assert scenarios.repetition_du_corpus(500, 180) == {
        "candidatures": 500,
        "documents_distincts": 180,
        "repetition_moyenne": 2.78,
    }
    assert scenarios.repetition_du_corpus(50, 180)["repetition_moyenne"] == 1.0


# --- plan de campagne -----------------------------------------------------


def test_plan_complet_est_la_matrice_de_la_carte() -> None:
    plan = campagne.plan_complet(["hr-50", "hr-100"], [2, 4, 8], 3)
    assert len(plan) == 2 * 3 * 3
    assert plan[0] == campagne.Point("hr-50", 2, 1)


def test_plan_complet_ne_fait_pas_varier_la_concurrence_du_sales() -> None:
    plan = campagne.plan_complet(["sales-30"], [2, 4, 8], 2)
    assert [p.concurrence for p in plan] == [0, 0]


def test_lire_points_et_estimation() -> None:
    plan = campagne.lire_points(["hr-50:4:2", "mixed:8:1"])
    assert [(p.scenario, p.concurrence, p.repetition) for p in plan] == [
        ("hr-50", 4, 1),
        ("hr-50", 4, 2),
        ("mixed", 8, 1),
    ]
    assert plan[0].estimation_usd() == pytest.approx(50 * mesures.COUT_ESTIME_CV_USD)
    # `mixed` paie 100 CV et DEUX passages de 30 questions (à vide + sous charge).
    assert plan[2].estimation_usd() == pytest.approx(
        100 * mesures.COUT_ESTIME_CV_USD + 60 * mesures.COUT_ESTIME_QUESTION_USD
    )


def test_lire_points_refuse_un_scenario_inconnu() -> None:
    with pytest.raises(ValueError, match="Scénario inconnu"):
        campagne.lire_points(["coach-10:4:1"])
    with pytest.raises(ValueError, match="scenario:concurrence:repetitions"):
        campagne.lire_points(["hr-50:4"])


def test_la_taille_du_lot_est_dans_le_nom_du_scenario() -> None:
    """Un lot de 6 CV ne peut pas se faire passer pour un lot de 500."""
    assert campagne.taille_du_lot("hr-500") == 500
    assert campagne.taille_du_lot("hr-6") == 6
    assert campagne.taille_du_lot("mixed") == campagne.CV_MIXED_PAR_DEFAUT
    assert campagne.taille_du_lot("mixed-6") == 6
    assert campagne.taille_du_lot("sales-30") == 0
    assert campagne.scenario_valide("hr-7") and not campagne.scenario_valide("hr")


def test_estimation_suit_le_nombre_de_questions_demande() -> None:
    petit = campagne.lire_points(["mixed-6:2:1"], questions=3)[0]
    assert petit.estimation_usd() == pytest.approx(
        6 * mesures.COUT_ESTIME_CV_USD + 6 * mesures.COUT_ESTIME_QUESTION_USD
    )


# --- agrégation commerciale ----------------------------------------------


def _question(secondes: float, statut: str = "final") -> dict[str, object]:
    return {
        "contexte": "a_vide",
        "id": "q",
        "statut": statut,
        "secondes": secondes,
        "appels_llm": 2,
        "outils_executes": 1,
        "llm_ms_total": int(secondes * 800),
        "outil_ms_total": int(secondes * 100),
        "autre_ms": int(secondes * 100),
    }


def test_agreger_sales_ignore_les_tours_non_aboutis_dans_la_latence() -> None:
    resultats = [_question(1.0), _question(2.0), _question(99.0, "erreur: LLMError")]
    bloc = scenarios.agreger_sales(resultats)
    assert bloc["questions"] == 3
    assert bloc["tours_aboutis"] == 2
    assert bloc["etapes"]["non_aboutis"] == 1
    assert bloc["latence"]["max_secondes"] == 2.0


def test_agreger_sales_sans_tour_abouti_ne_fabrique_pas_de_percentile() -> None:
    bloc = scenarios.agreger_sales([_question(1.0, "erreur: X")])
    assert bloc["latence"]["p95_secondes"] is None
    assert bloc["par_etape_ms"]["llm_moyen"] is None


# --- assemblage du rapport ------------------------------------------------


def _campagne_factice(questions: list[dict[str, object]]) -> campagne.Campagne:
    return campagne.Campagne(
        sortie=Path("/tmp"),
        budget=mesures.Budget(plafond_usd=1.0),
        graine=1,
        topologie=worker_charge.SEPAREE,
        surcharges={},
        runs=[],
        questions=questions,
        light=[],
        taches=[],
        journal=[],
    )


def test_les_questions_sont_regroupees_par_famille_de_scenario() -> None:
    """`mixed` et `mixed-6` sont le même scénario à deux tailles : le rapport
    doit les retrouver, sinon le critère du p95 sort « NON MESURÉ » alors que
    la mesure a bien eu lieu."""
    fausse = _campagne_factice(
        [
            {"scenario": "mixed-6", "contexte": "a_vide", "secondes": 1.0},
            {"scenario": "mixed-6", "contexte": "sous_charge", "secondes": 2.0},
            {"scenario": "sales-30", "contexte": "a_vide", "secondes": 3.0},
        ]
    )
    assert len(campagne._questions_par(fausse, "mixed", "a_vide")) == 1
    assert len(campagne._questions_par(fausse, "mixed", "sous_charge")) == 1
    assert len(campagne._questions_par(fausse, "sales-30", "a_vide")) == 1
    assert campagne._questions_par(fausse, "mixed", "inconnu") == []


# --- topologie des workers -------------------------------------------------


def test_la_topologie_separee_monte_un_worker_par_file() -> None:
    """La topologie mesurée par défaut est celle du VPS : `heavy` à la
    concurrence du point, `light` à la concurrence du déploiement. Mesurer un
    worker unique donnerait une famine que la production ne connaît pas."""
    groupe = worker_charge.GroupeWorkers(worker_charge.SEPAREE, 8, cwd=Path("/tmp"), journal=None)
    assert [w.files for w in groupe.workers] == ["heavy", "light"]
    assert [w.concurrence for w in groupe.workers] == [8, worker_charge.CONCURRENCE_LIGHT]
    assert len(set(groupe.noms)) == 2


def test_la_topologie_unique_reste_disponible_pour_documenter_la_famine() -> None:
    groupe = worker_charge.GroupeWorkers(worker_charge.UNIQUE, 8, cwd=Path("/tmp"))
    assert [w.files for w in groupe.workers] == ["heavy,light"]


def test_une_topologie_inconnue_est_refusee_avant_de_depenser() -> None:
    with pytest.raises(ValueError, match="Topologie inconnue"):
        worker_charge.GroupeWorkers("mixte", 4, cwd=Path("/tmp"))


def test_les_workers_du_groupe_ne_se_prennent_pas_pour_des_intrus(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Avec deux workers, le contrôle d'intrus porte sur le groupe entier :
    sinon le second démarrage échouerait en voyant le premier."""
    monkeypatch.setattr(
        worker_charge.celery_app.control,
        "ping",
        lambda timeout=3.0: [{"benchh8@vps": {"ok": "pong"}}, {"autre@vps": {"ok": "pong"}}],
    )
    assert worker_charge.workers_etrangers(["benchh8", "benchl2"]) == ["autre@vps"]
    assert worker_charge.workers_etrangers("benchl2") == ["benchh8@vps", "autre@vps"]


def test_la_memoire_releve_la_somme_des_arbres_de_workers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Un seul arbre relevé sous-estimerait la mémoire que la machine doit
    fournir quand deux workers tournent."""
    monkeypatch.setattr(worker_charge, "arbre", lambda racine: [racine])
    monkeypatch.setattr(worker_charge, "rss_ko", lambda pid: 1024 * pid)
    releve = worker_charge.ReleveMemoire()
    releve.ajouter(1, 2)
    assert releve.pic_mo == 3.0


def test_le_verdict_de_famine_nomme_la_topologie_mesuree() -> None:
    """Une famine constatée alors que `light` a son propre worker n'a pas la
    même cause qu'une famine sur worker unique : le rapport doit le dire."""
    famine = {
        "famine": True,
        "sondes_sans_reponse": 3,
        "p95_charge_s": 11.72,
        "p95_vide_s": 0.07,
    }
    unique = campagne._phrase_famine(famine, worker_charge.UNIQUE)
    separee = campagne._phrase_famine(famine, worker_charge.SEPAREE)
    assert "Un worker unique" in unique
    assert "son propre worker" in separee
    assert worker_charge.CONCURRENCE_LIGHT == 2
