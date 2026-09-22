"""Métriques du harnais : fonctions pures, sans base ni modèle.

Tout ce qui se calcule sans appeler quoi que ce soit vit ici, pour que les
chiffres du chapitre 8 soient testables à la main sur de petits exemples. Les
suites, elles, ne font qu'appeler le code de production et ranger les résultats.

Aucune dépendance scientifique : Spearman sur 180 points ne justifie pas
d'ajouter scipy et numpy au projet, et une implémentation de vingt lignes se
relit dans un mémoire.
"""

from __future__ import annotations

import math
import unicodedata
from collections import Counter
from collections.abc import Iterable, Sequence


def rangs(valeurs: Sequence[float]) -> list[float]:
    """Rangs croissants, avec rang MOYEN pour les ex aequo.

    Les ex aequo comptent : la strate « hors profil » du jeu doré vaut 0 pour
    tout le monde (règle éliminatoire), soit 45 valeurs identiques. Leur donner
    des rangs arbitraires fabriquerait une corrélation qui n'existe pas.
    """
    indexes = sorted(range(len(valeurs)), key=lambda i: valeurs[i])
    sortie = [0.0] * len(valeurs)
    i = 0
    while i < len(indexes):
        j = i
        while j + 1 < len(indexes) and valeurs[indexes[j + 1]] == valeurs[indexes[i]]:
            j += 1
        rang_moyen = (i + j) / 2 + 1
        for k in range(i, j + 1):
            sortie[indexes[k]] = rang_moyen
        i = j + 1
    return sortie


def spearman(a: Sequence[float], b: Sequence[float]) -> float | None:
    """Corrélation de rang de Spearman. None si elle n'a pas de sens.

    Calculée comme un Pearson sur les rangs (et non par la formule 1 - 6Σd²/…,
    qui n'est valable que sans ex aequo). None quand il y a moins de trois
    points ou quand une des deux séries est constante : dans ce cas, aucune
    corrélation n'est définie, et renvoyer 0 laisserait croire à une absence de
    lien mesurée.
    """
    if len(a) != len(b):
        raise ValueError("Deux séries de longueurs différentes")
    if len(a) < 3:
        return None
    ra, rb = rangs(a), rangs(b)
    moy_a, moy_b = sum(ra) / len(ra), sum(rb) / len(rb)
    num = sum((x - moy_a) * (y - moy_b) for x, y in zip(ra, rb, strict=True))
    den_a = math.sqrt(sum((x - moy_a) ** 2 for x in ra))
    den_b = math.sqrt(sum((y - moy_b) ** 2 for y in rb))
    if den_a == 0 or den_b == 0:
        return None
    return round(num / (den_a * den_b), 4)


def precision_top_k(
    scores_ia: dict[str, float], scores_ref: dict[str, float], k: int
) -> float | None:
    """Part des K premiers de l'IA qui figurent dans les K premiers de la
    référence. None si moins de K candidats notés.

    Les ex aequo de la référence sont départagés par le nom de fichier, de
    façon déterministe : sans cela, la métrique bougerait d'un rejeu à l'autre
    sans que rien n'ait changé. La limite est réelle et dite dans le rapport,
    elle ne touche que la frontière du K.
    """
    communs = [nom for nom in scores_ia if nom in scores_ref]
    if len(communs) < k or k <= 0:
        return None
    haut_ia = sorted(communs, key=lambda n: (-scores_ia[n], n))[:k]
    haut_ref = sorted(communs, key=lambda n: (-scores_ref[n], n))[:k]
    return round(len(set(haut_ia) & set(haut_ref)) / k, 4)


def exactitude(attendus: Sequence[bool], obtenus: Sequence[bool]) -> dict[str, float | int]:
    """Exactitude d'une décision binaire, avec le détail des deux erreurs.

    Sur les critères éliminatoires, les deux erreurs ne coûtent pas la même
    chose : écarter un bon candidat (faux négatif) est invisible et grave,
    laisser passer un candidat hors profil (faux positif) se voit en entretien.
    """
    if len(attendus) != len(obtenus):
        raise ValueError("Deux séries de longueurs différentes")
    vp = sum(1 for a, o in zip(attendus, obtenus, strict=True) if a and o)
    vn = sum(1 for a, o in zip(attendus, obtenus, strict=True) if not a and not o)
    fp = sum(1 for a, o in zip(attendus, obtenus, strict=True) if not a and o)
    fn = sum(1 for a, o in zip(attendus, obtenus, strict=True) if a and not o)
    total = len(attendus)
    return {
        "exactitude": round((vp + vn) / total, 4) if total else 0.0,
        "vrais_positifs": vp,
        "vrais_negatifs": vn,
        "faux_positifs": fp,
        "faux_negatifs": fn,
        "total": total,
    }


def f1(attendus: Iterable[str], obtenus: Iterable[str]) -> dict[str, float]:
    """Précision, rappel et F1 sur deux ENSEMBLES de noms d'outils.

    Un outil appelé deux fois reste un outil appelé : on compare des ensembles,
    pas des listes. Le nombre d'appels est mesuré à part (`etapes`).
    """
    a, o = set(attendus), set(obtenus)
    if not a and not o:
        return {"precision": 1.0, "rappel": 1.0, "f1": 1.0}
    vrais = len(a & o)
    precision = vrais / len(o) if o else 0.0
    rappel = vrais / len(a) if a else 0.0
    score = 2 * precision * rappel / (precision + rappel) if precision + rappel else 0.0
    return {"precision": round(precision, 4), "rappel": round(rappel, 4), "f1": round(score, 4)}


def percentile(valeurs: Sequence[float], p: float) -> float | None:
    """Percentile par interpolation linéaire (p entre 0 et 100).

    p95 sur 30 questions tombe entre deux observations : l'interpolation évite
    de faire passer le seuil pour franchi à cause d'un arrondi vers le bas.
    """
    if not valeurs:
        return None
    triees = sorted(valeurs)
    if len(triees) == 1:
        return round(triees[0], 2)
    position = (p / 100) * (len(triees) - 1)
    bas = math.floor(position)
    haut = math.ceil(position)
    if bas == haut:
        return round(triees[bas], 2)
    return round(triees[bas] + (triees[haut] - triees[bas]) * (position - bas), 2)


def bornes_de_strate(scores_par_strate: dict[str, list[float]]) -> dict[str, float]:
    """Frontières de classement, déduites des scores de RÉFÉRENCE.

    Le jeu doré a des plages disjointes (hors profil 0, limite 29-51, bon 60-78,
    excellent 89-98). Plutôt que d'écrire ces nombres en dur dans le harnais,
    on prend le milieu de chaque intervalle vide : la matrice de confusion
    s'ajuste toute seule si le jeu doré évolue, et aucun seuil arbitraire ne
    vient d'ailleurs que de la donnée.

    Renvoie la borne INFÉRIEURE de chaque strate, hors `hors_profil` (qui est
    décidée par la règle éliminatoire, pas par un seuil).
    """
    ordre = ["hors_profil", "limite", "bon", "excellent"]
    presentes = [s for s in ordre if scores_par_strate.get(s)]
    bornes: dict[str, float] = {}
    for basse, haute in zip(presentes, presentes[1:], strict=False):
        if basse == "hors_profil":
            continue
        bornes[haute] = (max(scores_par_strate[basse]) + min(scores_par_strate[haute])) / 2
    if "limite" in presentes:
        bornes.setdefault("limite", 0.5)
    return bornes


def strate_predite(score: float, must_have_ok: bool, bornes: dict[str, float]) -> str:
    """Strate déduite d'un score d'IA, avec les mêmes frontières que ci-dessus."""
    if not must_have_ok or score <= 0:
        return "hors_profil"
    for nom in ("excellent", "bon", "limite"):
        if nom in bornes and score >= bornes[nom]:
            return nom
    return "limite"


def matrice_de_confusion(
    couples: Sequence[tuple[str, str]], strates: Sequence[str]
) -> dict[str, dict[str, int]]:
    """Matrice attendu -> prédit, cases vides comprises (lisible telle quelle
    dans un tableau du mémoire)."""
    compte = Counter(couples)
    return {
        attendu: {predit: compte.get((attendu, predit), 0) for predit in strates}
        for attendu in strates
    }


def normaliser(texte: str) -> str:
    """Minuscules sans accents ni ponctuation d'espacement.

    Sert à chercher une entité ou une citation dans une réponse rédigée :
    « Norelec » et « norelec » sont la même entreprise, et une preuve recopiée
    avec une apostrophe typographique reste la même preuve.
    """
    sans_accents = unicodedata.normalize("NFD", texte.lower())
    sans_accents = "".join(c for c in sans_accents if unicodedata.category(c) != "Mn")
    remplacements = {"’": "'", "‘": "'", "“": '"', "”": '"', " ": " "}
    for avant, apres in remplacements.items():
        sans_accents = sans_accents.replace(avant, apres)
    return " ".join(sans_accents.split())


def contient(texte: str, aiguille: str) -> bool:
    """Présence d'une chaîne dans un texte, à la normalisation près."""
    return normaliser(aiguille) in normaliser(texte)


def moyenne(valeurs: Sequence[float]) -> float | None:
    return round(sum(valeurs) / len(valeurs), 4) if valeurs else None
