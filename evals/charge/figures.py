"""Figures brutes du chapitre 8, dessinées depuis les CSV de la campagne.

Trois figures, pas une de plus : celles que la carte demande. Aucune ne
réagrège quoi que ce soit — elles tracent les colonnes des CSV telles quelles,
pour qu'une figure et un tableau ne puissent pas raconter deux histoires.

matplotlib est importé DANS les fonctions : une campagne doit pouvoir produire
ses CSV sur une machine où la bibliothèque n'est pas installée, et ne perdre
que ses figures.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

# Palette sobre et lisible en niveaux de gris : un mémoire s'imprime.
COULEURS = ("#2b6cb0", "#c05621", "#2f855a")


def _matplotlib() -> Any:
    import matplotlib

    matplotlib.use("Agg")  # aucun serveur graphique sur le VPS
    import matplotlib.pyplot as plt

    return plt


def debit_vs_concurrence(points: dict[int, list[float]], chemin: Path, titre: str) -> Path | None:
    """Débit (CV/min) en fonction de `worker_concurrency`.

    Les répétitions sont tracées en barres d'étendue (min-max), pas en
    écart-type : c'est l'étendue que le critère de reproductibilité regarde.
    """
    if not points:
        return None
    plt = _matplotlib()
    concurrences = sorted(points)
    moyennes = [sum(points[c]) / len(points[c]) for c in concurrences]
    bas = [m - min(points[c]) for c, m in zip(concurrences, moyennes, strict=True)]
    haut = [max(points[c]) - m for c, m in zip(concurrences, moyennes, strict=True)]

    figure, axes = plt.subplots(figsize=(6, 4))
    axes.errorbar(
        concurrences, moyennes, yerr=[bas, haut], marker="o", capsize=4, color=COULEURS[0]
    )
    axes.set_xlabel("worker_concurrency")
    axes.set_ylabel("Débit (CV notés par minute)")
    axes.set_title(titre)
    axes.set_xticks(concurrences)
    axes.grid(True, linestyle=":", linewidth=0.6)
    figure.tight_layout()
    chemin.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(chemin, dpi=150)
    plt.close(figure)
    return chemin


def latence_par_etape(series: dict[str, dict[str, float]], chemin: Path, titre: str) -> Path | None:
    """Décomposition d'un tour d'agent : modèle, outils, reste."""
    if not series:
        return None
    plt = _matplotlib()
    etiquettes = list(series)
    parts = ("llm_moyen", "outil_moyen", "autre_moyen")
    noms = ("Appels au modèle", "Outils CRM", "Reste (boucle, base)")

    figure, axes = plt.subplots(figsize=(6, 4))
    bas = [0.0] * len(etiquettes)
    for index, (part, nom) in enumerate(zip(parts, noms, strict=True)):
        valeurs = [float(series[e].get(part) or 0.0) for e in etiquettes]
        axes.bar(etiquettes, valeurs, bottom=bas, label=nom, color=COULEURS[index])
        bas = [b + v for b, v in zip(bas, valeurs, strict=True)]
    axes.set_ylabel("Millisecondes (moyenne par tour)")
    axes.set_title(titre)
    axes.legend()
    axes.grid(True, axis="y", linestyle=":", linewidth=0.6)
    figure.tight_layout()
    chemin.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(chemin, dpi=150)
    plt.close(figure)
    return chemin


def cout_par_lot(lots: dict[str, float], chemin: Path, titre: str) -> Path | None:
    """Coût total observé par scénario RH."""
    if not lots:
        return None
    plt = _matplotlib()
    etiquettes = list(lots)
    figure, axes = plt.subplots(figsize=(6, 4))
    barres = axes.bar(etiquettes, [lots[e] for e in etiquettes], color=COULEURS[0])
    axes.bar_label(barres, fmt="%.2f")
    axes.set_ylabel("Coût du lot (USD)")
    axes.set_title(titre)
    axes.grid(True, axis="y", linestyle=":", linewidth=0.6)
    figure.tight_layout()
    chemin.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(chemin, dpi=150)
    plt.close(figure)
    return chemin
