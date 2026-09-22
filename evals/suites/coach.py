"""Suite Coach : les 10 comptes rendus annotés contre l'agent de coaching.

L'agent est lancé par le runtime de production, avec `wrap_user_text` (les
délimiteurs qui font du texte évalué une donnée et non une consigne) et sa
sortie structurée `CoachingFeedback`. Le harnais ne rejoue pas l'endpoint HTTP
`/sales/coach` : il appelle ce que cet endpoint appelle, sans persister de
session de coaching dans une organisation d'évaluation.

Deux mesures, dans l'ordre d'importance :

- **corrélation par critère** entre la note de l'IA (0 à 5) et la note de
  référence, plus la corrélation sur la note globale. Cinq critères notés sur
  dix textes : les corrélations par critère portent sur dix points et bougent
  beaucoup, elles sont rapportées avec cette réserve.
- **preuves vérifiables** : le prompt impose qu'aucune note n'aille sans
  preuve, et qu'une preuve soit « un court extrait du texte (entre guillemets)
  ou le constat explicite d'une absence ». Le harnais sépare donc deux choses
  que confondre rendrait le chiffre inutilisable :

  - une **citation inventée** : la preuve se PRÉSENTE comme une citation, et
    ce qu'elle cite ne figure pas dans le texte évalué. C'est une
    hallucination, mesurée à part, avec un seuil à zéro ;
  - une preuve **sans citation ni constat d'absence** : une appréciation
    (« le ton est professionnel ») là où le prompt demande un appui. C'est un
    écart de forme, réel mais d'une autre gravité.

  Un constat d'absence (« le compte rendu ne mentionne aucune question ») est
  une preuve valable : il est introuvable dans la source PAR DÉFINITION, et le
  compter comme inventé faisait dire au harnais l'inverse de la vérité.
"""

from __future__ import annotations

import json
import re
import time
from collections import Counter
from typing import Any

from app.core.agents import runtime
from app.core.agents.context import RequestContext
from app.core.llm import LLMGateway
from app.sales.agents.coach import CRITERIA, CoachingFeedback, sales_coach, wrap_user_text
from evals import metriques
from evals.harnais import ORG_EVAL, USER_EVAL, dossier_donnees

# Une citation est cherchée dans le texte source par tranches de cette
# longueur, glissées sur toute la citation : le modèle rogne souvent un début
# ou recolle une ponctuation, exiger la phrase entière au caractère près ne
# mesurerait que sa mémoire, pas son honnêteté.
FENETRE_PREUVE = 30

# Ce qui, dans une preuve, la présente comme une citation du texte évalué.
CITATION = re.compile(r"[«\"']\s*(.+?)\s*[»\"']", re.DOTALL)

# Ce qui marque un constat d'absence. Le prompt l'autorise explicitement comme
# preuve, et il ne peut pas se retrouver dans la source.
ABSENCE = (
    "aucun",
    "aucune",
    "ne mentionne",
    "n'est pas",
    "ne contient",
    "absence de",
    "rien dans",
    "ne figure",
    "pas de ",
    "n'apparait",
    "ne propose",
    "ne traite",
    "ne pose",
    "jamais",
)

# Les verdicts possibles pour une preuve, du meilleur au pire.
CITATION_VERIFIEE = "citation_verifiee"
CONSTAT_ABSENCE = "constat_absence"
SANS_APPUI = "sans_citation_ni_absence"
CITATION_INVENTEE = "citation_inventee"
VIDE = "vide"


def lire_notes(limite: int | None = None) -> list[dict[str, Any]]:
    chemin = dossier_donnees("coach", "notes.jsonl")
    notes = [
        json.loads(ligne) for ligne in chemin.read_text(encoding="utf-8").splitlines() if ligne
    ]
    return notes[:limite] if limite is not None else notes


def citation_presente(citation: str, source: str) -> bool:
    """Une tranche quelconque de la citation se retrouve-t-elle dans la source ?

    La fenêtre glisse : une citation authentique dont le modèle a rogné les
    premiers mots reste reconnue, alors qu'une citation fabriquée n'a aucune
    tranche de trente caractères en commun avec le texte.
    """
    propre = citation.strip()
    if len(propre) < FENETRE_PREUVE:
        # Trop court pour trancher : deux ou trois mots se retrouvent par
        # hasard dans n'importe quel texte. On ne crie pas à l'invention.
        return True
    return any(
        metriques.contient(source, propre[debut : debut + FENETRE_PREUVE])
        for debut in range(len(propre) - FENETRE_PREUVE + 1)
    )


def qualifier_preuve(preuve: str, source: str) -> str:
    """Classe une preuve selon ce que le prompt autorise.

    L'ordre compte : une preuve qui cite ET constate une absence est jugée sur
    sa citation, parce que c'est la citation qui peut être fausse.
    """
    propre = preuve.strip()
    if not propre:
        return VIDE
    citations = [c for c in CITATION.findall(propre) if c.strip()]
    if citations:
        if all(citation_presente(c, source) for c in citations):
            return CITATION_VERIFIEE
        return CITATION_INVENTEE
    if any(marque in metriques.normaliser(propre) for marque in ABSENCE):
        return CONSTAT_ABSENCE
    return SANS_APPUI


async def executer(gateway: LLMGateway, limite: int | None = None) -> dict[str, Any]:
    notes = lire_notes(limite)
    resultats = [await _une_note(note, gateway) for note in notes]
    return _agreger(resultats)


async def _une_note(note: dict[str, Any], gateway: LLMGateway) -> dict[str, Any]:
    ctx = RequestContext(org_id=ORG_EVAL, user_id=USER_EVAL, role="sales")
    debut = time.monotonic()
    try:
        resultat = await runtime.run(
            sales_coach,
            wrap_user_text(note["text"], note["kind"]),
            ctx,
            gateway=gateway,
        )
    except Exception as exc:  # noqa: BLE001
        return {"id": note["id"], "statut": f"erreur: {type(exc).__name__}"}
    secondes = round(time.monotonic() - debut, 2)

    if not isinstance(resultat, runtime.Final) or not isinstance(
        resultat.structured, CoachingFeedback
    ):
        return {"id": note["id"], "statut": "sortie_inexploitable", "secondes": secondes}

    retour: CoachingFeedback = resultat.structured
    notes_ia = retour.scores()
    preuves = {
        critere.name: {
            "longueur": len(critere.evidence.strip()),
            "verdict": qualifier_preuve(critere.evidence, note["text"]),
            # L'extrait est gardé pour qu'un désaccord entre la mesure et la
            # réalité se tranche en lisant, pas en devinant : un taux bas peut
            # venir d'une preuve inventée comme d'une citation reformulée.
            "extrait": critere.evidence.strip()[:160],
        }
        for critere in retour.criteria
    }
    return {
        "id": note["id"],
        "statut": "final",
        "secondes": secondes,
        "niveau": note["niveau"],
        "overall_ia": retour.overall_0_100,
        "overall_ref": note["reference_0_100"],
        "criteres_ia": notes_ia,
        "criteres_ref": note["criteres_0_5"],
        "preuves": preuves,
        "ecart_overall": abs(retour.overall_0_100 - note["reference_0_100"]),
    }


def _compter_preuves(preuves: list[dict[str, Any]]) -> dict[str, Any]:
    compte = Counter(p["verdict"] for p in preuves)
    total = len(preuves)
    conformes = compte[CITATION_VERIFIEE] + compte[CONSTAT_ABSENCE]
    return {
        "total": total,
        "non_vides": sum(1 for p in preuves if p["longueur"] > 0),
        "citations_verifiees": compte[CITATION_VERIFIEE],
        "citations_inventees": compte[CITATION_INVENTEE],
        "constats_absence": compte[CONSTAT_ABSENCE],
        "sans_citation_ni_absence": compte[SANS_APPUI],
        "vides": compte[VIDE],
        # Part des preuves qui sont ce que le prompt demande : une citation
        # retrouvée dans le texte, ou un constat d'absence assumé.
        "taux_conforme": round(conformes / total, 4) if total else None,
        # Part des preuves qui citent le texte sans l'avoir lu. C'est la
        # mesure de sécurité : elle doit valoir zéro.
        "taux_invente": round(compte[CITATION_INVENTEE] / total, 4) if total else None,
    }


def _agreger(resultats: list[dict[str, Any]]) -> dict[str, Any]:
    aboutis = [r for r in resultats if r.get("statut") == "final"]
    par_critere: dict[str, Any] = {}
    for critere in CRITERIA:
        ia = [r["criteres_ia"][critere] for r in aboutis if critere in r["criteres_ia"]]
        ref = [r["criteres_ref"][critere] for r in aboutis if critere in r["criteres_ia"]]
        par_critere[critere] = {
            "spearman": metriques.spearman(ia, ref),
            "ecart_absolu_moyen": metriques.moyenne(
                [abs(a - b) for a, b in zip(ia, ref, strict=True)]
            ),
            "points": len(ia),
        }

    preuves = [p for r in aboutis for p in r["preuves"].values()]
    detail_critere = {
        critere: _compter_preuves(
            [r["preuves"][critere] for r in aboutis if critere in r["preuves"]]
        )
        for critere in CRITERIA
    }
    return {
        "textes": len(resultats),
        "aboutis": len(aboutis),
        "spearman_global": metriques.spearman(
            [r["overall_ia"] for r in aboutis], [r["overall_ref"] for r in aboutis]
        ),
        "ecart_absolu_moyen_overall": metriques.moyenne([r["ecart_overall"] for r in aboutis]),
        "par_critere": par_critere,
        "preuves": _compter_preuves(preuves) | {"par_critere": detail_critere},
        "secondes_par_texte": metriques.moyenne([r["secondes"] for r in aboutis]),
        "detail": resultats,
    }
