"""Tests du jeu doré versionné dans `evals/data` (carte [INFRA] Jeu de données).

Ce qui est vérifié ici n'est pas du code applicatif mais une **donnée de
référence** : si elle dérive, toutes les mesures du chapitre 8 deviennent
incomparables. D'où quatre propriétés tenues par des tests :

1. `make gen-data` régénère le jeu à l'identique, octet pour octet ;
2. le score de référence de chaque CV est bien celui que `compute_overall`
   calcule à partir des niveaux de construction — aucune note posée à la main,
   aucune note produite par un modèle ;
3. les 190 fichiers s'ouvrent vraiment (180 CV exploitables, 3 scannés,
   2 corrompus, 5 porteurs d'une injection) ;
4. les jeux Sales et Coach sont cohérents avec le bac à sable et avec la
   grille du coach.
"""

import csv
import json
from collections import Counter
from datetime import date
from pathlib import Path

import pytest

from app.hr.criteria import Criteria
from app.hr.extraction import MIN_USEFUL_CHARS, ExtractionError, NeedsOCR, extract_text
from app.hr.schemas import CandidateAssessment, align_with_grid, compute_overall
from scripts import gen_cvs
from scripts.crm_seed import charger, lire, lire_questions, resoudre_date

JEU = gen_cvs.DESTINATION
OFFRES = ("developpeur-full-stack", "commercial-b2b", "assistant-rh")
OUTILS_LECTURE = {
    "find_account",
    "find_contact",
    "get_opportunity",
    "search_activities",
    "get_account_context",
}
CRITERES_COACH = (
    "decouverte_des_besoins",
    "gestion_des_objections",
    "proposition_de_valeur",
    "prochaine_etape",
    "ton_et_concision",
)


def _labels(slug: str) -> list[dict[str, str]]:
    with (JEU / "hr" / slug / "labels.csv").open(encoding="utf-8", newline="") as flux:
        return list(csv.DictReader(flux))


def _niveaux(slug: str) -> dict[str, dict[str, int]]:
    contenu: dict[str, dict[str, int]] = json.loads(
        (JEU / "hr" / slug / "niveaux.json").read_text(encoding="utf-8")
    )
    return contenu


def _grille(slug: str) -> Criteria:
    return Criteria.model_validate_json(
        (JEU / "hr" / slug / "grille.json").read_text(encoding="utf-8")
    )


# --- 1. reproductibilité -------------------------------------------------


def test_gen_data_regenere_a_l_identique(tmp_path: Path) -> None:
    """Deux générations à graine égale donnent les mêmes octets.

    La comparaison porte sur le jeu COMMITTÉ : elle prouve à la fois le
    déterminisme du générateur et le fait que les fichiers versionnés sont
    bien ceux que `make gen-data` produit aujourd'hui.
    """
    gen_cvs.generer(tmp_path, gen_cvs.GRAINE)

    produits = {p.relative_to(tmp_path) for p in tmp_path.rglob("*") if p.is_file()}
    attendus = {
        p.relative_to(JEU)
        for p in JEU.rglob("*")
        if p.is_file()
        and p.name not in {"offre.md", "grille.json", "briques.json", "README.md"}
        # Les sources écrites à la main ne sont pas regénérées, le reste si.
        and p.parts[len(JEU.parts) :][0] in {"hr", "adverse"}
        and p.name != "injection.txt"
    }
    assert produits == attendus

    differents = [
        str(relatif)
        for relatif in sorted(produits)
        if (tmp_path / relatif).read_bytes() != (JEU / relatif).read_bytes()
    ]
    assert differents == []


# --- 2. le label est une vérité de construction --------------------------


@pytest.mark.parametrize("slug", OFFRES)
def test_score_de_reference_recalculable_par_compute_overall(slug: str) -> None:
    """Chaque `score_ref_0_100` se rejoue depuis `niveaux.json` et la grille.

    C'est la garantie centrale de la carte : le label n'est pas un jugement
    (ni humain, ni modèle), c'est le résultat de la formule de production
    appliquée à un profil contrôlé. Un écart d'un point signifierait que la
    référence et le pipeline ne parlent plus de la même règle.
    """
    grille = _grille(slug)
    niveaux_par_cv = _niveaux(slug)
    for ligne in _labels(slug):
        niveaux = niveaux_par_cv[ligne["candidate_file"]]
        appreciation = CandidateAssessment(
            criteria=[
                {"name": nom, "score_0_5": niveau, "evidence": "niveau de construction"}  # type: ignore[list-item]
                for nom, niveau in niveaux.items()
            ],
            confidence=1.0,
        )
        lignes, rates = align_with_grid(appreciation, grille.weights(), grille.must_haves())
        assert compute_overall(lignes, rates) == int(ligne["score_ref_0_100"])
        assert ligne["must_have_ok"] == ("non" if rates else "oui")


@pytest.mark.parametrize("slug", OFFRES)
def test_strates_separees_et_equilibrees(slug: str) -> None:
    """15 CV par strate, et des plages de score disjointes et ordonnées."""
    labels = _labels(slug)
    assert len(labels) == 4 * gen_cvs.PAR_STRATE
    par_strate = Counter(ligne["strate"] for ligne in labels)
    assert par_strate == {strate: gen_cvs.PAR_STRATE for strate in gen_cvs.STRATES}

    scores = {
        strate: [int(x["score_ref_0_100"]) for x in labels if x["strate"] == strate]
        for strate in gen_cvs.STRATES
    }
    assert min(scores["excellent"]) > max(scores["bon"])
    assert min(scores["bon"]) > max(scores["limite"])
    assert min(scores["limite"]) > max(scores["hors_profil"])
    # Un éliminatoire manqué ramène la note à 0 : c'est toute la strate.
    assert set(scores["hors_profil"]) == {0}
    assert all(x["must_have_ok"] == "non" for x in labels if x["strate"] == "hors_profil")


@pytest.mark.parametrize("slug", OFFRES)
def test_grille_conforme_au_schema_de_production(slug: str) -> None:
    """La grille du jeu doré est celle que le pipeline sait manipuler."""
    grille = _grille(slug)
    assert len(grille.must_haves()) >= 1
    briques = json.loads((JEU / "hr" / slug / "briques.json").read_text(encoding="utf-8"))
    for critere in grille.criteria:
        niveaux = briques["briques"][critere.name]
        assert len(niveaux) == 6
        assert niveaux[0] == ""  # niveau 0 = le CV n'en parle pas
        assert all(niveau.strip() for niveau in niveaux[1:])


# --- 3. les fichiers s'ouvrent vraiment ----------------------------------


@pytest.mark.parametrize("slug", OFFRES)
def test_les_cv_sont_ouvrables_et_dans_les_deux_formats(slug: str) -> None:
    labels = _labels(slug)
    fichiers = sorted((JEU / "hr" / slug / "cv").iterdir())
    assert len(fichiers) == 60
    assert {f.name for f in fichiers} == {ligne["candidate_file"] for ligne in labels}

    formats = Counter(f.suffix for f in fichiers)
    assert formats == {".pdf": 30, ".docx": 30}
    # Chaque strate doit contenir des deux formats, sinon le format devient un
    # indice corrélé au niveau du candidat.
    for strate in gen_cvs.STRATES:
        suffixes = Counter(
            Path(x["candidate_file"]).suffix for x in labels if x["strate"] == strate
        )
        assert suffixes[".pdf"] >= 3 and suffixes[".docx"] >= 3

    for fichier in fichiers:
        texte = extract_text(fichier.read_bytes(), fichier.suffix.lstrip("."))
        assert len(texte) >= MIN_USEFUL_CHARS


def test_cas_adverses_complets_et_conformes() -> None:
    dossier = JEU / "adverse"
    with (dossier / "labels.csv").open(encoding="utf-8", newline="") as flux:
        manifeste = list(csv.DictReader(flux))
    assert Counter(ligne["cas"] for ligne in manifeste) == {
        "injection_de_consigne": 5,
        "cv_scanne_sans_texte": 3,
        "fichier_corrompu": 2,
    }

    for ligne in manifeste:
        fichier = dossier / ligne["candidate_file"]
        kind = fichier.suffix.lstrip(".")
        if ligne["cas"] == "injection_de_consigne":
            texte = extract_text(fichier.read_bytes(), kind)
            # Le PDF coupe les lignes : on compare sur un texte remis à plat.
            plat = " ".join(texte.split())
            assert " ".join(gen_cvs.INJECTION.split()) in plat
            assert int(ligne["score_ref_0_100"]) >= 0
        elif ligne["cas"] == "cv_scanne_sans_texte":
            with pytest.raises(NeedsOCR):
                extract_text(fichier.read_bytes(), kind)
        else:
            with pytest.raises(ExtractionError):
                extract_text(fichier.read_bytes(), kind)


@pytest.mark.parametrize("slug", OFFRES)
def test_formulaire_de_double_annotation_pret_et_vide(slug: str) -> None:
    """10 % du lot attend une seconde annotation HUMAINE : les colonnes de
    notation doivent être vides, sinon la mesure de cohérence est truquée."""
    chemin = JEU / "hr" / slug / "double_annotation.csv"
    with chemin.open(encoding="utf-8", newline="") as flux:
        lecteur = csv.DictReader(flux)
        lignes = list(lecteur)
        assert lecteur.fieldnames is not None
        assert "score_ref_0_100_2" in lecteur.fieldnames
    assert len(lignes) == 6  # 10 % de 60
    connus = {ligne["candidate_file"] for ligne in _labels(slug)}
    for ligne in lignes:
        assert ligne["candidate_file"] in connus
        assert ligne["score_ref_0_100_2"] == ""
        assert ligne["must_have_ok_2"] == ""
        assert ligne["annotateur"] == ""


# --- 4. jeux Sales et Coach ---------------------------------------------


async def test_questions_commerciales_rejouables_sur_le_bac_a_sable() -> None:
    """Les 30 questions portent sur des données réellement chargeables.

    On charge la graine dans un `FakeCRM` : chaque entité attendue doit avoir
    reçu un identifiant, et chaque fait doré doit être vrai dans le CRM — pas
    seulement dans le fichier de graine.
    """
    from app.sales.crm import FakeCRM

    crm = FakeCRM()
    graine = lire()
    refs = await charger(crm, graine)
    par_ref = {r["ref"]: r for r in graine["records"]}

    questions = lire_questions()
    assert len(questions) == 30
    assert len({q["id"] for q in questions}) == 30

    for question in questions:
        assert question["question"].strip()
        assert set(question["expected_tools"]) <= OUTILS_LECTURE
        assert question["expected_tools"], question["id"]
        for entite in question["expected_entities"]:
            assert entite in refs, f"{question['id']} : entité inconnue {entite}"
        for fait in question["gold_facts"]:
            enregistrement = await crm.get(par_ref[fait["ref"]]["object"], refs[fait["ref"]])
            attendu = fait["value"]
            if isinstance(attendu, str):  # les dates dorées sont relatives
                attendu = resoudre_date(attendu, date.today())
            assert enregistrement[fait["field"]] == attendu, question["id"]
            assert fait["texte"].strip()

    # Des questions sans réponse : l'agent doit savoir dire qu'il ne sait pas.
    sans_donnee = [q for q in questions if q.get("attendu_aucune_donnee")]
    assert len(sans_donnee) >= 3
    assert all(not q["gold_facts"] for q in sans_donnee)


def test_comptes_rendus_de_coaching_annotes() -> None:
    lignes = (JEU / "coach" / "notes.jsonl").read_text(encoding="utf-8").splitlines()
    notes = [json.loads(ligne) for ligne in lignes if ligne.strip()]
    assert len(notes) == 10
    assert Counter(note["niveau"] for note in notes) == {"bon": 3, "moyen": 4, "faible": 3}

    for note in notes:
        criteres = note["criteres_0_5"]
        assert tuple(criteres) == CRITERES_COACH
        assert all(0 <= valeur <= 5 for valeur in criteres.values())
        # Le score global se déduit des cinq critères : même principe que côté
        # RH, la note d'ensemble n'est jamais posée à la main.
        attendu = round(100 * sum(criteres.values()) / (5 * len(CRITERES_COACH)))
        assert note["reference_0_100"] == attendu
        assert note["text"].strip() and note["rationale"].strip()

    assert (JEU / "coach" / "injection.txt").read_text(encoding="utf-8").strip()
