"""Prompts versionnés (ADR-010) : `prompts/<agent>/v<N>.md` à la racine du dépôt.

Un changement de prompt = un NOUVEAU fichier v<N+1>.md, jamais d'écrasement.
La version retournée est journalisée dans `llm_calls` (prompt_version) pour
la reproductibilité des expériences du mémoire.
"""

import re
from pathlib import Path

# backend/app/core/llm/prompts.py -> racine du dépôt / prompts
_PROMPTS_DIR = Path(__file__).resolve().parents[4] / "prompts"

_VERSION_RE = re.compile(r"v(\d+)\.md")


def load_prompt(
    agent: str, version: int | None = None, base_dir: Path | None = None
) -> tuple[str, int]:
    """Retourne (texte, version). Sans `version` : la plus récente."""
    agent_dir = (base_dir or _PROMPTS_DIR) / agent
    if version is None:
        versions = sorted(
            int(m.group(1)) for f in agent_dir.glob("v*.md") if (m := _VERSION_RE.fullmatch(f.name))
        )
        if not versions:
            raise FileNotFoundError(
                f"Aucun prompt versionné pour l'agent {agent!r} dans {agent_dir}"
            )
        version = versions[-1]
    return (agent_dir / f"v{version}.md").read_text(encoding="utf-8"), version
