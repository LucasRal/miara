"""Chargement du bac à sable CRM du jeu doré (`evals/data/sales/crm_seed.json`).

Le jeu de questions commerciales n'a de sens que si les données sur lesquelles
il porte sont les mêmes à chaque rejeu. Le fichier de graine décrit ces données
avec deux conventions qui le rendent portable :

- **références symboliques** (`@acc_norelec`) plutôt qu'identifiants : c'est le
  CRM qui attribue les siens au chargement, ici comme dans une organisation
  Salesforce de bac à sable. Le harnais compare donc des références, pas des
  identifiants tirés d'un enregistrement d'hier ;
- **dates relatives** (`today-10`, `today+45`) : les fenêtres d'activités de 30
  et 90 jours des outils de lecture restent valables quel que soit le jour du
  rejeu.

    from scripts.crm_seed import charger, lire
    refs = await charger(crm, lire())
"""

import json
import re
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from app.sales.crm.port import CRMPort

RACINE = Path(__file__).resolve().parents[2]
GRAINE = RACINE / "evals" / "data" / "sales" / "crm_seed.json"
QUESTIONS = RACINE / "evals" / "data" / "sales" / "questions.jsonl"

_RELATIF = re.compile(r"^today([+-]\d+)?$")


def lire(chemin: Path = GRAINE) -> dict[str, Any]:
    contenu: dict[str, Any] = json.loads(chemin.read_text(encoding="utf-8"))
    return contenu


def lire_questions(chemin: Path = QUESTIONS) -> list[dict[str, Any]]:
    lignes = chemin.read_text(encoding="utf-8").splitlines()
    return [json.loads(ligne) for ligne in lignes if ligne.strip()]


def resoudre_date(valeur: str, aujourdhui: date) -> str:
    """`today-10` -> date ISO. Toute autre chaîne est rendue telle quelle."""
    trouve = _RELATIF.match(valeur)
    if trouve is None:
        return valeur
    return (aujourdhui + timedelta(days=int(trouve.group(1) or 0))).isoformat()


def resoudre_champs(
    champs: dict[str, Any], refs: dict[str, str], aujourdhui: date
) -> dict[str, Any]:
    resolus: dict[str, Any] = {}
    for nom, valeur in champs.items():
        if isinstance(valeur, str) and valeur.startswith("@"):
            resolus[nom] = refs[valeur[1:]]
        elif isinstance(valeur, str):
            resolus[nom] = resoudre_date(valeur, aujourdhui)
        else:
            resolus[nom] = valeur
    return resolus


async def charger(
    crm: CRMPort, graine: dict[str, Any] | None = None, aujourdhui: date | None = None
) -> dict[str, str]:
    """Peuple `crm` et renvoie la table de correspondance référence -> id.

    L'ordre du fichier fait foi : un enregistrement ne peut référencer que des
    enregistrements déjà créés, ce qui évite toute passe de résolution.
    """
    graine = graine or lire()
    jour = aujourdhui or date.today()
    refs: dict[str, str] = {}
    for enregistrement in graine["records"]:
        champs = resoudre_champs(enregistrement["fields"], refs, jour)
        refs[enregistrement["ref"]] = await crm.create(enregistrement["object"], champs)
    return refs
