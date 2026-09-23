"""Catalogue des outils de l'agent commercial, lu dans les objets `Tool`.

Importe `READ_TOOLS` et `WRITE_TOOLS` et lit, pour chaque outil, son nom, son
drapeau `is_write` et les champs de son schema Pydantic d'arguments. Verifie au
passage qu'aucun schema n'expose `org_id` ni un identifiant de connexion
(contrainte 2 de l'architecture) : le cas echeant, la figure le signale.

    cd backend && uv run python ../thesis/figures/gen/catalogue_outils.py
"""

from __future__ import annotations

import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(RACINE / "backend"))

from app.sales.tools import READ_TOOLS, WRITE_TOOLS  # noqa: E402

INTERDITS = {"org_id", "organization_id", "access_token", "instance_url", "credentials"}


def champs(outil) -> str:
    noms = list(outil.args_schema.model_fields)
    return ", ".join(noms) if noms else "aucun argument"


def main() -> int:
    fuites = [
        (o.name, c)
        for o in [*READ_TOOLS, *WRITE_TOOLS]
        for c in o.args_schema.model_fields
        if c in INTERDITS
    ]
    lignes = [
        "%% Genere par thesis/figures/gen/catalogue_outils.py - ne pas editer a la main",
        "flowchart TB",
        '    ctx["RequestContext<br/>org_id, user_id, role, trace_id, call_id"]',
        '    subgraph lecture["outils de lecture (executes sans confirmation)"]',
        "        direction TB",
    ]
    for i, outil in enumerate(READ_TOOLS):
        lignes.append(f'        r{i}["{outil.name}<br/>{champs(outil)}"]')
    lignes.append("    end")
    lignes.append('    subgraph ecriture["outils d ecriture (confirmation humaine, ADR-009)"]')
    lignes.append("        direction TB")
    for i, outil in enumerate(WRITE_TOOLS):
        lignes.append(f'        w{i}["{outil.name}<br/>{champs(outil)}"]')
    lignes.append("    end")
    verdict = (
        "aucun argument d outil ne porte d identite ni de secret"
        if not fuites
        else f"FUITE : {fuites}"
    )
    lignes.append(f'    ctx --> verdict["{verdict}"]')
    lignes.append("    verdict --> lecture")
    lignes.append("    verdict --> ecriture")
    print("\n".join(lignes))
    return 1 if fuites else 0


if __name__ == "__main__":
    raise SystemExit(main())
