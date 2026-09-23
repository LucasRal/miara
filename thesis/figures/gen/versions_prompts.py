"""Inventaire des prompts versionnes presents dans prompts/ (ADR-010).

Pour chaque agent : les versions livrees, la taille de chacune et celle que le
chargeur `load_prompt` retient (la plus elevee). Lu sur le disque, jamais
recopie.

    python3 thesis/figures/gen/versions_prompts.py
"""

from __future__ import annotations

import re
from pathlib import Path

RACINE = Path(__file__).resolve().parents[3]
PROMPTS = RACINE / "prompts"
VERSION = re.compile(r"^v(\d+)\.md$")


def main() -> int:
    lignes = [
        "%% Genere par thesis/figures/gen/versions_prompts.py - ne pas editer a la main",
        "flowchart LR",
    ]
    for i, dossier in enumerate(sorted(p for p in PROMPTS.iterdir() if p.is_dir())):
        versions = sorted(
            (int(m.group(1)), f)
            for f in dossier.iterdir()
            if (m := VERSION.match(f.name))
        )
        if not versions:
            continue
        cle = f"g{i}"
        lignes.append(f'    subgraph {cle}["prompts/{dossier.name}/"]')
        lignes.append("        direction LR")
        precedent = None
        for numero, fichier in versions:
            mots = len(fichier.read_text(encoding="utf-8").split())
            noeud = f"{cle}v{numero}"
            actif = " (chargee)" if numero == versions[-1][0] else ""
            lignes.append(f'        {noeud}["v{numero}<br/>{mots} mots{actif}"]')
            if precedent:
                lignes.append(f"        {precedent} --> {noeud}")
            precedent = noeud
        lignes.append("    end")
    print("\n".join(lignes))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
