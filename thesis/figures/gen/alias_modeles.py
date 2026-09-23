"""Carte des alias de modeles, lue dans backend/config/llm.yaml.

Un alias, son modele principal et ses replis. Rien n'est recopie a la main :
si la configuration change, la figure change (ADR-011).

    cd backend && uv run python ../thesis/figures/gen/alias_modeles.py
"""

from __future__ import annotations

from pathlib import Path

import yaml

RACINE = Path(__file__).resolve().parents[3]
CONFIG = RACINE / "backend" / "config" / "llm.yaml"


def modele(valeur) -> str:
    return valeur["model"] if isinstance(valeur, dict) else str(valeur)


def main() -> int:
    config = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    defauts = config.get("defaults", {})
    lignes = [
        "%% Genere par thesis/figures/gen/alias_modeles.py - ne pas editer a la main",
        "flowchart LR",
        f'    code["code applicatif<br/>(alias seulement)"] --> routeur["LiteLLM Router<br/>timeout {defauts.get("timeout")} s'
        f' - {defauts.get("max_retries")} reessais"]',
    ]
    for i, (alias, spec) in enumerate(config["aliases"].items()):
        cle = f"a{i}"
        lignes.append(f'    routeur --> {cle}["{alias}"]')
        lignes.append(f'    {cle} --> {cle}p["{modele(spec["primary"])}"]')
        for j, repli in enumerate(spec.get("fallbacks") or []):
            lignes.append(f'    {cle}p -. repli .-> {cle}f{j}["{modele(repli)}"]')
    print("\n".join(lignes))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
