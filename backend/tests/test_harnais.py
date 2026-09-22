"""Tests du harnais d'évaluation (`evals/`), sans base ni modèle.

Un harnais qui mesure faux est pire que pas de harnais : il produit des
chiffres qu'on défend en soutenance. Tout ce qui se calcule sans appeler un
modèle est donc vérifié ici sur des exemples dont la réponse est connue à la
main, y compris les cas dégénérés (ex aequo, série constante, effectif trop
petit) qui sont exactement ceux du jeu doré.

Les suites elles-mêmes ne sont pas testées ici : elles appellent le pipeline
de production, elles sont vérifiées en l'exécutant (`make eval`).
"""

import json
import math
from pathlib import Path

import pytest

from evals import compare, juge, metriques, resume, seuils, versions
from evals.suites import coach as suite_coach
from evals.suites import hr as suite_hr

# --- Rangs et corrélation ---------------------------------------------------


def test_rangs_moyens_sur_les_ex_aequo() -> None:
    # Trois valeurs identiques occupent les rangs 2, 3 et 4 : chacune reçoit 3.
    assert metriques.rangs([10, 5, 5, 5, 1]) == [5.0, 3.0, 3.0, 3.0, 1.0]


def test_spearman_ordre_parfait_et_ordre_inverse() -> None:
    assert metriques.spearman([1, 2, 3, 4], [10, 20, 30, 40]) == 1.0
    assert metriques.spearman([1, 2, 3, 4], [40, 30, 20, 10]) == -1.0


def test_spearman_connu_a_la_main() -> None:
    # Une seule inversion sur cinq points : rho = 1 - 6*2/(5*24) = 0,9.
    assert metriques.spearman([1, 2, 3, 4, 5], [1, 2, 3, 5, 4]) == pytest.approx(0.9)


def test_spearman_indefini_plutot_que_zero() -> None:
    """Une série constante n'a pas de corrélation : 0 se lirait comme « aucun
    lien mesuré », ce qui est faux. On renvoie None, le rapport écrit n. d."""
    assert metriques.spearman([1, 1, 1, 1], [1, 2, 3, 4]) is None
    assert metriques.spearman([1, 2], [2, 1]) is None


def test_spearman_refuse_des_longueurs_differentes() -> None:
    with pytest.raises(ValueError):
        metriques.spearman([1, 2, 3], [1, 2])


# --- Précision top-K --------------------------------------------------------


def test_precision_top_k_compte_l_intersection() -> None:
    ia = {"a": 90.0, "b": 80.0, "c": 70.0, "d": 10.0}
    ref = {"a": 95.0, "b": 85.0, "d": 60.0, "c": 20.0}
    assert metriques.precision_top_k(ia, ref, 2) == 1.0
    assert metriques.precision_top_k(ia, ref, 3) == pytest.approx(2 / 3, abs=1e-4)


def test_precision_top_k_absente_si_trop_peu_de_candidats() -> None:
    assert metriques.precision_top_k({"a": 1.0}, {"a": 1.0}, 10) is None


def test_precision_top_k_departage_les_ex_aequo_de_facon_stable() -> None:
    """Deux appels sur les mêmes données donnent le même chiffre."""
    ia = {"a": 50.0, "b": 50.0, "c": 50.0}
    ref = {"a": 50.0, "b": 50.0, "c": 50.0}
    assert metriques.precision_top_k(ia, ref, 2) == metriques.precision_top_k(ia, ref, 2) == 1.0


# --- Décisions binaires et outils ------------------------------------------


def test_exactitude_separe_les_deux_erreurs() -> None:
    resultat = metriques.exactitude([True, True, False, False], [True, False, True, False])
    assert resultat["exactitude"] == 0.5
    assert resultat["faux_negatifs"] == 1  # un bon candidat écarté
    assert resultat["faux_positifs"] == 1  # un candidat hors profil laissé


def test_f1_sur_des_ensembles_d_outils() -> None:
    resultat = metriques.f1(["find_account", "search_activities"], ["find_account", "find_contact"])
    assert resultat["precision"] == 0.5
    assert resultat["rappel"] == 0.5
    assert resultat["f1"] == 0.5


def test_f1_ignore_les_appels_repetes() -> None:
    assert metriques.f1(["a"], ["a", "a", "a"])["f1"] == 1.0


def test_f1_parfait_quand_rien_n_est_attendu_ni_appele() -> None:
    assert metriques.f1([], [])["f1"] == 1.0


# --- Percentiles ------------------------------------------------------------


def test_percentile_interpole() -> None:
    assert metriques.percentile([1, 2, 3, 4], 50) == 2.5
    assert metriques.percentile([1, 2, 3, 4], 0) == 1
    assert metriques.percentile([1, 2, 3, 4], 100) == 4


def test_percentile_vide() -> None:
    assert metriques.percentile([], 95) is None


# --- Strates ----------------------------------------------------------------


def test_bornes_de_strate_prend_le_milieu_des_intervalles_vides() -> None:
    bornes = metriques.bornes_de_strate(
        {"hors_profil": [0], "limite": [29, 51], "bon": [60, 78], "excellent": [89, 98]}
    )
    assert bornes["bon"] == pytest.approx(55.5)
    assert bornes["excellent"] == pytest.approx(83.5)


def test_strate_predite_suit_les_bornes_et_la_regle_eliminatoire() -> None:
    bornes = {"limite": 0.5, "bon": 55.5, "excellent": 83.5}
    assert metriques.strate_predite(95, True, bornes) == "excellent"
    assert metriques.strate_predite(70, True, bornes) == "bon"
    assert metriques.strate_predite(30, True, bornes) == "limite"
    # Un éliminatoire manqué prime sur la note, même haute.
    assert metriques.strate_predite(95, False, bornes) == "hors_profil"


def test_matrice_de_confusion_montre_les_cases_vides() -> None:
    matrice = metriques.matrice_de_confusion([("bon", "bon"), ("bon", "limite")], ("bon", "limite"))
    assert matrice["bon"] == {"bon": 1, "limite": 1}
    assert matrice["limite"] == {"bon": 0, "limite": 0}


# --- Recherche de texte -----------------------------------------------------


def test_contient_ignore_accents_casse_et_apostrophes() -> None:
    assert metriques.contient("L'opportunité Norelec est en Négociation.", "norelec")
    assert metriques.contient("Le coût s’élève à 84 000 euros", "cout s'eleve")
    assert not metriques.contient("Aucune opportunité", "Norelec")


# --- Seuils -----------------------------------------------------------------


def test_seuil_min_viole_et_seuil_max_tenu() -> None:
    violations, respectes = seuils.verifier(
        {"hr": {"global": {"spearman": 0.5, "taux_echec": 0.01}}},
        [
            {"chemin": "hr.global.spearman", "min": 0.75},
            {"chemin": "hr.global.taux_echec", "max": 0.05},
        ],
    )
    assert [v["chemin"] for v in violations] == ["hr.global.spearman"]
    assert [r["chemin"] for r in respectes] == ["hr.global.taux_echec"]


def test_seuil_d_une_suite_non_executee_est_ignore() -> None:
    violations, respectes = seuils.verifier(
        {"hr": {"global": {"spearman": 0.9}}},
        [{"chemin": "sales.latence.p95_secondes", "max": 3.0}],
    )
    assert violations == [] and respectes == []


def test_metrique_absente_dans_une_suite_executee_est_une_violation() -> None:
    """Le cas qui, sans cela, passerait inaperçu : la suite a tourné mais la
    métrique n'a pas pu être calculée."""
    violations, _ = seuils.verifier(
        {"hr": {"global": {"spearman": None}}},
        [{"chemin": "hr.global.spearman", "min": 0.75}],
    )
    assert violations[0]["motif"].startswith("métrique absente")


def test_le_fichier_de_seuils_du_depot_est_lisible_et_complet() -> None:
    from evals import SEUILS

    charges = seuils.lire(SEUILS)
    assert len(charges) >= 8
    assert all(s.get("pourquoi") for s in charges), "chaque seuil doit dire pourquoi il existe"


# --- Comparaison de deux rapports ------------------------------------------


def _rapport(spearman: float, p95: float) -> dict:
    return {
        "harnais": {"date": "2026-09-22T10:00:00+00:00", "sha": "abc1234", "prompt_versions": {}},
        "suites": {
            "hr": {"global": {"spearman": spearman}},
            "sales": {"latence": {"p95_secondes": p95}},
        },
    }


def test_comparaison_connait_le_sens_des_metriques() -> None:
    lignes = {
        ligne["chemin"]: ligne for ligne in compare.comparer(_rapport(0.7, 4.0), _rapport(0.8, 3.0))
    }
    assert lignes["hr.global.spearman"]["verdict"] == "mieux"  # monter est bon
    assert lignes["sales.latence.p95_secondes"]["verdict"] == "mieux"  # baisser aussi


def test_comparaison_signale_un_rapport_partiel() -> None:
    avant = _rapport(0.7, 3.0)
    apres = _rapport(0.8, 3.0)
    apres["harnais"]["limite"] = 5
    rendu = compare.rendre(avant, apres)
    assert "partiel" in rendu.lower()


def test_comparaison_supporte_une_metrique_absente() -> None:
    avant = _rapport(0.7, 3.0)
    avant["suites"]["hr"]["global"]["spearman"] = None
    lignes = {ligne["chemin"]: ligne for ligne in compare.comparer(avant, _rapport(0.8, 3.0))}
    assert lignes["hr.global.spearman"]["verdict"] == "incomparable"


# --- Juge et relecture ------------------------------------------------------


def _jugement(cle: str, present: bool) -> juge.Jugement:
    return juge.Jugement(
        cle=cle, question="q ?", fait="un fait", reponse="une réponse", present=present
    )


def test_echantillon_de_relecture_est_deterministe() -> None:
    jugements = [_jugement(f"q{i}", i % 3 == 0) for i in range(20)]
    premier = [j.cle for j in juge.echantillon(jugements)]
    second = [j.cle for j in juge.echantillon(list(reversed(jugements)))]
    assert premier == second


def test_echantillon_met_les_verdicts_negatifs_en_premier() -> None:
    jugements = [_jugement("a", True), _jugement("b", False), _jugement("c", True)]
    assert juge.echantillon(jugements, part=1 / 3)[0].cle == "b"


def test_feuille_de_relecture_contient_le_fait_et_la_reponse(tmp_path: Path) -> None:
    chemin = tmp_path / "relecture.md"
    nombre = juge.ecrire_feuille(chemin, [_jugement("q01-f1", False)], part=1.0)
    texte = chemin.read_text(encoding="utf-8")
    assert nombre == 1
    assert "q01-f1" in texte and "un fait" in texte and "une réponse" in texte
    assert "accord / desaccord" in texte


# --- Résumé markdown --------------------------------------------------------


def test_resume_ecrit_les_tableaux_attendus(tmp_path: Path) -> None:
    rapport = {
        "harnais": {
            "version": resume.VERSION_RAPPORT,
            "date": "2026-09-22T10:00:00+00:00",
            "sha": "abc1234",
            "suites": ["hr"],
            "limite": None,
            "prompt_versions": {"hr.score": 1},
        },
        "suites": {
            "hr": {
                "offres": {
                    "offre-a": {
                        "notes": 60,
                        "echecs": 0,
                        "spearman": 0.81,
                        "precision_top_10": 0.9,
                        "precision_top_20": 0.85,
                        "must_have": {"exactitude": 0.95},
                        "secondes_par_cv": 8.2,
                        "cout_par_cv_usd": 0.009,
                        "confusion": None,
                    }
                },
                "global": {
                    "notes": 60,
                    "echecs": 0,
                    "spearman": 0.81,
                    "exactitude_must_have": 0.95,
                    "ecart_absolu_moyen": 6.1,
                    "secondes_par_cv": 8.2,
                    "cout_usd": 0.54,
                    "cout_par_cv_usd": 0.009,
                    "confusion": {"bon": {"bon": 15}},
                },
            }
        },
        "juge": {"verdicts": 0},
        "seuils": {"respectes": 3, "violations": []},
    }
    chemin = tmp_path / "rapport.md"
    resume.ecrire_resume(chemin, rapport)
    texte = chemin.read_text(encoding="utf-8")
    assert "0,810" in texte  # virgule décimale, pas de point
    assert "Tous les seuils sont tenus" in texte
    assert "Présélection RH" in texte


def test_resume_ecrit_n_d_plutot_qu_un_zero() -> None:
    assert resume.nombre(None) == "n. d."
    assert resume.pourcent(None) == "n. d."
    assert resume.nombre(0.5) == "0,50"


# --- Preuves du coach -------------------------------------------------------


SOURCE_COACH = (
    "Le client a demandé un délai de paiement à soixante jours, ce qui bloque "
    "la signature avant la fin du trimestre."
)


def test_citation_retrouvee_dans_le_texte() -> None:
    assert (
        suite_coach.qualifier_preuve("« Le client a demandé un délai de paiement »", SOURCE_COACH)
        == suite_coach.CITATION_VERIFIEE
    )


def test_citation_absente_du_texte_est_une_invention() -> None:
    assert (
        suite_coach.qualifier_preuve("« Le client a signé le contrat sur-le-champ »", SOURCE_COACH)
        == suite_coach.CITATION_INVENTEE
    )


def test_constat_d_absence_est_une_preuve_valable() -> None:
    """Le prompt l'autorise, et il est introuvable dans la source par nature."""
    assert (
        suite_coach.qualifier_preuve(
            "le compte rendu ne mentionne aucune prochaine étape", SOURCE_COACH
        )
        == suite_coach.CONSTAT_ABSENCE
    )


def test_appreciation_sans_appui_est_distinguee_d_une_invention() -> None:
    """Une appréciation est un écart de forme, pas une hallucination."""
    assert (
        suite_coach.qualifier_preuve("le ton reste professionnel et direct", SOURCE_COACH)
        == suite_coach.SANS_APPUI
    )


def test_preuve_vide() -> None:
    assert suite_coach.qualifier_preuve("   ", SOURCE_COACH) == suite_coach.VIDE


def test_citation_rognee_au_debut_reste_verifiee() -> None:
    """La fenêtre glisse : un modèle qui coupe les premiers mots reste honnête."""
    assert (
        suite_coach.qualifier_preuve(
            "« un délai de paiement à soixante jours, ce qui bloque la signature »",
            SOURCE_COACH,
        )
        == suite_coach.CITATION_VERIFIEE
    )


def test_le_comptage_separe_les_deux_fautes() -> None:
    preuves = [
        {"verdict": suite_coach.CITATION_VERIFIEE, "longueur": 40},
        {"verdict": suite_coach.CONSTAT_ABSENCE, "longueur": 30},
        {"verdict": suite_coach.SANS_APPUI, "longueur": 20},
        {"verdict": suite_coach.CITATION_INVENTEE, "longueur": 35},
    ]
    compte = suite_coach._compter_preuves(preuves)
    assert compte["taux_conforme"] == 0.5
    assert compte["taux_invente"] == 0.25
    assert compte["citations_inventees"] == 1


# --- Jeu doré ---------------------------------------------------------------


def test_les_trois_offres_du_jeu_dore_sont_lisibles() -> None:
    offres = suite_hr.offres_disponibles()
    assert len(offres) == 3
    for offre in offres:
        labels = suite_hr.lire_labels(suite_hr.dossier_donnees("hr", offre) / "labels.csv")
        assert len(labels) == 60
        assert all(0 <= v["score_ref"] <= 100 for v in labels.values())


def test_les_grilles_du_jeu_dore_se_chargent_dans_le_schema_de_production() -> None:
    from app.hr.criteria import Criteria

    for offre in suite_hr.offres_disponibles():
        chemin = suite_hr.dossier_donnees("hr", offre) / "grille.json"
        grille = Criteria.model_validate_json(chemin.read_text(encoding="utf-8"))
        assert grille.must_haves(), "chaque grille doit avoir au moins un éliminatoire"


def test_les_questions_portent_des_outils_qui_existent() -> None:
    from app.sales.tools import READ_TOOLS, WRITE_TOOLS
    from scripts.crm_seed import lire_questions

    connus = {t.name for t in (*READ_TOOLS, *WRITE_TOOLS)}
    for question in lire_questions():
        assert set(question["expected_tools"]) <= connus, question["id"]


# --- Épinglage de version de prompt ----------------------------------------


def test_prompts_epingles_force_la_version_puis_restaure() -> None:
    from app.core.llm import prompts as module_prompts

    _, derniere = module_prompts.load_prompt("hr.score")
    with versions.prompts_epingles({"hr.score": 1}):
        _, epinglee = module_prompts.load_prompt("hr.score")
        assert epinglee == 1
    _, apres = module_prompts.load_prompt("hr.score")
    assert apres == derniere


def test_versions_utilisees_ignore_un_agent_sans_prompt() -> None:
    assert versions.versions_utilisees(("agent.inexistant",)) == {}


# --- Config LLM -------------------------------------------------------------


def test_la_surcharge_d_alias_retire_les_replis() -> None:
    from evals.harnais import charger_config_llm

    config = charger_config_llm({"hr.score": "fournisseur/modele-de-test"})
    assert config["aliases"]["hr.score"] == {"primary": "fournisseur/modele-de-test"}
    assert "fallbacks" not in config["aliases"]["hr.score"]


def test_la_surcharge_d_un_alias_inconnu_echoue() -> None:
    from evals.harnais import charger_config_llm

    with pytest.raises(SystemExit):
        charger_config_llm({"alias.qui.n.existe.pas": "modele"})


def test_le_juge_a_son_propre_alias_dans_la_config() -> None:
    from evals.harnais import charger_config_llm

    assert juge.ALIAS_JUGE in charger_config_llm()["aliases"]


# --- Rapport sérialisable ---------------------------------------------------


def test_un_rapport_se_relit_en_json(tmp_path: Path) -> None:
    """Le rapport contient des Decimal et des UUID : il doit rester lisible."""
    from decimal import Decimal
    from uuid import uuid4

    brut = {"cout": Decimal("0.123456"), "run": uuid4(), "nan_evite": 1.0}
    chemin = tmp_path / "r.json"
    chemin.write_text(json.dumps(brut, default=str, ensure_ascii=False), encoding="utf-8")
    relu = json.loads(chemin.read_text(encoding="utf-8"))
    assert relu["cout"] == "0.123456"
    assert not math.isnan(relu["nan_evite"])


# --- Dépouillement de la feuille de relecture -------------------------------

FEUILLE = """# Relecture des verdicts du juge

## 1. q01-f1

- **Verdict du juge** : absent
- **Ton avis** : accord / desaccord : accord

## 2. q02-f1

- **Verdict du juge** : présent
- **Ton avis** : accord / desaccord : desaccord
"""


def test_feuille_remplie_donne_le_taux_d_accord() -> None:
    releve = juge.depouiller_feuille(FEUILLE)
    assert releve == {
        "cas": 2,
        "accords": 1,
        "desaccords": 1,
        "manquants": [],
        "taux_accord": 0.5,
    }


def test_feuille_a_moitie_remplie_ne_donne_aucun_taux() -> None:
    """Relire les cas faciles et laisser les autres gonflerait le taux."""
    releve = juge.depouiller_feuille(FEUILLE.replace(": desaccord", ":"))
    assert releve["manquants"] == ["q02-f1"]
    assert releve["taux_accord"] is None


def test_un_avis_mal_orthographie_est_un_cas_non_relu() -> None:
    releve = juge.depouiller_feuille(FEUILLE.replace("desaccord : accord", "desaccord : daccord"))
    assert "q01-f1" in releve["manquants"]
    assert releve["taux_accord"] is None


def test_un_rapport_d_une_version_anterieure_est_refuse(tmp_path: Path) -> None:
    """Deux définitions d'une même métrique ne doivent jamais finir dans un tableau."""
    ancien = {"harnais": {"version": 1}, "suites": {}, "juge": {}, "seuils": {}}
    with pytest.raises(resume.RapportTropAncien):
        resume.ecrire_resume(tmp_path / "x.md", ancien)
