"""Suite Sales : les 30 questions du jeu doré contre l'agent commercial.

L'agent exécuté est celui de production (`sales_assistant`), lancé par le
runtime borné avec ses vrais outils. Le CRM est un `FakeCRM` peuplé par la
graine du jeu doré, rechargé à neuf pour chaque exécution : une question ne
doit jamais voir ce qu'une autre a écrit.

Quatre mesures par question :

- **outils** : F1 entre les outils attendus et les outils réellement exécutés.
  Un outil de plus n'est pas une erreur grave (l'agent a cherché ailleurs),
  un outil manquant l'est : précision et rappel sont donc rapportés séparément.
- **entités** : les enregistrements que la réponse doit citer, cherchés par
  leur intitulé dans le texte final. Vérification textuelle, sans modèle.
- **faits dorés** : jugés un par un par `eval.judge`, avec relecture humaine
  sur échantillon.
- **latence et étapes** : durée du tour complet et nombre d'appels au modèle.

Les trois questions marquées `attendu_aucune_donnee` sont l'inverse des
autres : la bonne réponse est de dire qu'il n'y a rien. Elles sont jugées à
part, parce qu'elles mesurent ce que l'agent s'interdit d'inventer.
"""

from __future__ import annotations

import time
from typing import Any

from app.core.agents import runtime
from app.core.agents.context import RequestContext
from app.core.llm import LLMGateway
from app.sales.agents.assistant import sales_assistant
from app.sales.crm.factory import clear_fake, register_fake
from app.sales.crm.fake import FakeCRM
from evals import metriques
from evals.harnais import ORG_EVAL, USER_EVAL
from evals.juge import Jugement, juger
from scripts.crm_seed import charger, lire, lire_questions

CONSIGNE_ABSENCE = (
    "La réponse doit dire clairement qu'aucune donnée ne correspond dans le CRM, "
    "sans inventer de valeur ni la remplacer par un enregistrement approchant."
)


def intitules(graine: dict[str, Any]) -> dict[str, str]:
    """Référence -> intitulé lisible, tel qu'il apparaîtra dans une réponse.

    Un agent qui répond bien écrit « Norelec », pas l'identifiant que le CRM
    lui a attribué : c'est l'intitulé qu'on cherche dans le texte.
    """
    sortie: dict[str, str] = {}
    for enregistrement in graine["records"]:
        champs = enregistrement["fields"]
        for cle in ("Name", "Subject"):
            if isinstance(champs.get(cle), str):
                sortie[enregistrement["ref"]] = champs[cle]
                break
    return sortie


async def preparer_crm() -> tuple[FakeCRM, dict[str, str], dict[str, Any]]:
    graine = lire()
    crm = FakeCRM()
    refs = await charger(crm, graine)
    register_fake(ORG_EVAL, crm)
    return crm, refs, graine


async def executer(
    gateway: LLMGateway, limite: int | None = None, live: bool = False
) -> dict[str, Any]:
    """Rejoue les questions et renvoie le bloc de rapport.

    `live` est refusé ici : brancher le harnais sur un vrai bac à sable
    Salesforce demande une organisation connectée par OAuth et des écritures
    réelles, ce qui ne s'improvise pas depuis une ligne de commande. Le drapeau
    existe dans l'interface parce que la carte le demande ; il échoue
    franchement plutôt que de faire croire à une exécution distante.
    """
    if live:
        raise SystemExit(
            "--live n'est pas branché : la suite Sales tourne sur FakeCRM. "
            "Connecter une organisation Salesforce de bac à sable par l'écran "
            "Réglages, puis rejouer la graine avec scripts/crm_seed.py."
        )

    questions = lire_questions()
    if limite is not None:
        questions = questions[:limite]
    _, refs, graine = await preparer_crm()
    noms = intitules(graine)

    try:
        resultats = [await _une_question(q, gateway, refs, noms) for q in questions]
    finally:
        clear_fake(ORG_EVAL)

    return _agreger(resultats)


async def _une_question(
    question: dict[str, Any], gateway: LLMGateway, refs: dict[str, str], noms: dict[str, str]
) -> dict[str, Any]:
    """Un tour d'agent complet, mesuré."""
    evenements: list[dict[str, Any]] = []
    ctx = RequestContext(org_id=ORG_EVAL, user_id=USER_EVAL, role="sales")
    debut = time.monotonic()
    try:
        resultat = await runtime.run(
            sales_assistant,
            question["question"],
            ctx,
            gateway=gateway,
            observer=evenements.append,
        )
    except Exception as exc:  # noqa: BLE001 - une question ne doit pas couler la suite
        return {
            "id": question["id"],
            "question": question["question"],
            "statut": f"erreur: {type(exc).__name__}",
            "secondes": round(time.monotonic() - debut, 2),
            "outils": metriques.f1(question["expected_tools"], []),
            "entites": {"attendues": len(question["expected_entities"]), "trouvees": 0},
            "faits": [],
            "reponse": "",
        }
    secondes = round(time.monotonic() - debut, 2)

    executes = [e["tool"] for e in evenements if e["kind"] == "tool_exec" and e["tool"]]
    tentes = [e["tool"] for e in evenements if e["kind"] in {"tool_error"} and e["tool"]]
    appels_llm = sum(1 for e in evenements if e["kind"] == "llm_call")

    if isinstance(resultat, runtime.Final):
        reponse = resultat.content or ""
        statut = "final"
    elif isinstance(resultat, runtime.NeedsConfirmation):
        # Une question de LECTURE qui débouche sur une écriture est un écart :
        # on le compte comme tel plutôt que de le masquer.
        reponse = ""
        statut = f"confirmation_demandee:{resultat.tool}"
    else:
        reponse = ""
        statut = "limite_d_etapes"

    trouvees = [
        ref
        for ref in question["expected_entities"]
        if metriques.contient(reponse, noms.get(ref, ref)) or (ref in refs and refs[ref] in reponse)
    ]

    faits: list[Jugement] = []
    for numero, fait in enumerate(question.get("gold_facts", []), start=1):
        faits.append(
            await juger(
                gateway,
                cle=f"{question['id']}-f{numero}",
                question=question["question"],
                fait=fait["texte"],
                reponse=reponse,
            )
        )
    if question.get("attendu_aucune_donnee"):
        faits.append(
            await juger(
                gateway,
                cle=f"{question['id']}-absence",
                question=question["question"],
                fait=CONSIGNE_ABSENCE,
                reponse=reponse,
            )
        )

    return {
        "id": question["id"],
        "question": question["question"],
        "statut": statut,
        "secondes": secondes,
        "appels_llm": appels_llm,
        "outils_executes": sorted(set(executes)),
        "outils_en_erreur": sorted(set(tentes)),
        "outils": metriques.f1(question["expected_tools"], executes),
        "entites": {
            "attendues": len(question["expected_entities"]),
            "trouvees": len(trouvees),
            "manquantes": sorted(set(question["expected_entities"]) - set(trouvees)),
        },
        "attendu_aucune_donnee": bool(question.get("attendu_aucune_donnee")),
        "faits": [j.model_dump() for j in faits],
        "reponse": reponse,
        "_jugements": faits,
    }


def _agreger(resultats: list[dict[str, Any]]) -> dict[str, Any]:
    latences = [r["secondes"] for r in resultats if r["statut"] == "final"]
    attendues = sum(r["entites"]["attendues"] for r in resultats)
    trouvees = sum(r["entites"]["trouvees"] for r in resultats)

    ordinaires = [r for r in resultats if not r["attendu_aucune_donnee"]]
    absences = [r for r in resultats if r["attendu_aucune_donnee"]]
    faits_ordinaires = [f for r in ordinaires for f in r["faits"]]
    jugements = [j for r in resultats for j in r.get("_jugements", [])]

    for resultat in resultats:
        resultat.pop("_jugements", None)

    return {
        "questions": len(resultats),
        "tours_aboutis": len(latences),
        "outils": {
            "f1_moyen": metriques.moyenne([r["outils"]["f1"] for r in resultats]),
            "precision_moyenne": metriques.moyenne([r["outils"]["precision"] for r in resultats]),
            "rappel_moyen": metriques.moyenne([r["outils"]["rappel"] for r in resultats]),
            "questions_avec_tous_les_outils": sum(
                1 for r in resultats if r["outils"]["rappel"] == 1.0
            ),
        },
        "entites": {
            "attendues": attendues,
            "trouvees": trouvees,
            "rappel": round(trouvees / attendues, 4) if attendues else None,
        },
        "faits_dores": {
            "total": len(faits_ordinaires),
            "presents": sum(1 for f in faits_ordinaires if f["present"]),
            "taux": round(
                sum(1 for f in faits_ordinaires if f["present"]) / len(faits_ordinaires), 4
            )
            if faits_ordinaires
            else None,
        },
        "absence_de_donnee": {
            "questions": len(absences),
            "reussies": sum(1 for r in absences if all(f["present"] for f in r["faits"])),
        },
        "etapes": {
            "appels_llm_moyen": metriques.moyenne(
                [r.get("appels_llm", 0) for r in resultats if r["statut"] == "final"]
            ),
            "limites_d_etapes": sum(1 for r in resultats if r["statut"] == "limite_d_etapes"),
            "confirmations_inattendues": sum(
                1 for r in resultats if r["statut"].startswith("confirmation")
            ),
            "erreurs": sum(1 for r in resultats if r["statut"].startswith("erreur")),
        },
        "latence": {
            "p50_secondes": metriques.percentile(latences, 50),
            "p95_secondes": metriques.percentile(latences, 95),
            "max_secondes": max(latences) if latences else None,
        },
        "detail": resultats,
        "_jugements": jugements,
    }
