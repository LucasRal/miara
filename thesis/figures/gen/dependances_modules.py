"""Graphe des dependances entre paquets du backend, lu dans le code.

Analyse statique (module `ast`) de tous les fichiers de `backend/app/` : chaque
`import app.X...` est compte comme une arete du paquet contenant vers le paquet
importe. Sert a verifier la regle ADR-001 (`core` n'importe jamais un module
metier) sans la prendre pour acquise.

    python3 thesis/figures/gen/dependances_modules.py
"""

from __future__ import annotations

import ast
import sys
from collections import Counter
from pathlib import Path

RACINE = Path(__file__).resolve().parents[3]
APP = RACINE / "backend" / "app"

METIER = {"auth", "hr", "sales"}
TRANSVERSE = {"core"}


def paquet(chemin: Path) -> str:
    """Paquet de premier niveau sous `app/` ; `app` pour les fichiers racine."""
    relatif = chemin.relative_to(APP)
    return relatif.parts[0] if len(relatif.parts) > 1 else "app"


def cibles(arbre: ast.Module) -> set[str]:
    trouvees: set[str] = set()
    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.Import):
            noms = [alias.name for alias in noeud.names]
        elif isinstance(noeud, ast.ImportFrom) and noeud.module and noeud.level == 0:
            noms = [noeud.module]
        else:
            continue
        for nom in noms:
            morceaux = nom.split(".")
            if morceaux[0] == "app" and len(morceaux) > 1:
                trouvees.add(morceaux[1])
    return trouvees


def main() -> int:
    aretes: Counter[tuple[str, str]] = Counter()
    for fichier in sorted(APP.rglob("*.py")):
        if "__pycache__" in fichier.parts:
            continue
        source = paquet(fichier)
        for cible in cibles(ast.parse(fichier.read_text(encoding="utf-8"))):
            if cible != source and (cible in METIER | TRANSVERSE or cible == "app"):
                aretes[(source, cible)] += 1

    lignes = [
        "%% Genere par thesis/figures/gen/dependances_modules.py - ne pas editer a la main",
        "flowchart LR",
        "    subgraph composition[\"points de composition (hors paquets)\"]",
        "        app[\"app/ : main, celery_tasks, db_registry, queue, usage, dashboard\"]",
        "    end",
        "    subgraph metier[\"modules metier\"]",
        "        auth[\"auth/\"]",
        "        hr[\"hr/\"]",
        "        sales[\"sales/\"]",
        "    end",
        "    core[\"core/ : runtime, passerelle LLM, infra\"]",
    ]
    for (source, cible), poids in sorted(aretes.items()):
        lignes.append(f"    {source} -->|{poids}| {cible}")
    violations = [a for a in aretes if a[0] == "core" and a[1] in METIER]
    lignes.append(
        "    classDef ok fill:#eef7ee,stroke:#4a7c4a;"
        if not violations
        else "    classDef ok fill:#fdecea,stroke:#b03a2e;"
    )
    lignes.append("    class core ok")
    print("\n".join(lignes))
    if violations:
        print(f"ATTENTION : core importe {violations}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
