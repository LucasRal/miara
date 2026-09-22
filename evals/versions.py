"""Épinglage temporaire d'une version de prompt, pour comparer v1 et v2.

Le code de production appelle toujours `load_prompt(agent)` sans version : il
prend la plus récente, et c'est le bon comportement pour un produit. Comparer
deux versions demande donc de forcer la version le temps d'une exécution.

C'est fait ici par substitution de la fonction dans les modules qui l'ont
importée, et nulle part ailleurs : le dépôt ne gagne ni paramètre ni variable
d'environnement pour un besoin qui n'existe que dans le harnais. La liste des
modules concernés est explicite ; si un module se met à charger des prompts
sans figurer ici, l'épinglage ne le touchera pas, et la version réellement
utilisée restera visible dans `llm_calls.prompt_version`, qui est la source de
vérité du rapport.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from app.core.llm import prompts as module_prompts

# Modules qui font `from app.core.llm import load_prompt` et chargent un prompt
# pendant une évaluation.
PORTEURS = ("app.hr.pipeline", "app.core.agents.runtime")


@contextmanager
def prompts_epingles(versions: dict[str, int]) -> Iterator[None]:
    """`{"hr.score": 1}` : pendant le bloc, cet agent charge la version 1."""
    if not versions:
        yield
        return

    import importlib

    original = module_prompts.load_prompt

    def epingle(agent: str, version: int | None = None, base_dir: Path | None = None) -> Any:
        return original(agent, versions.get(agent, version), base_dir)

    # Typés `Any` : poser un attribut sur un module est refusé par le
    # vérificateur de types, à juste titre dans du code de production. Ici,
    # c'est précisément ce qu'on fait, et le bloc restaure l'état d'origine.
    modules: list[Any] = [importlib.import_module(nom) for nom in PORTEURS]
    source: Any = module_prompts
    anciens: list[tuple[Any, Any]] = [(m, getattr(m, "load_prompt", None)) for m in modules]
    for module, _ in anciens:
        module.load_prompt = epingle
    source.load_prompt = epingle
    try:
        yield
    finally:
        for module, ancien in anciens:
            if ancien is not None:
                module.load_prompt = ancien
        source.load_prompt = original


def versions_utilisees(agents: tuple[str, ...]) -> dict[str, int]:
    """Version effectivement chargée pour chaque agent, au moment de l'appel."""
    sortie: dict[str, int] = {}
    for agent in agents:
        try:
            _, version = module_prompts.load_prompt(agent)
        except FileNotFoundError:
            continue
        sortie[agent] = version
    return sortie
