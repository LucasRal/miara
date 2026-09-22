"""Harnais d'évaluation Miara : rejoue le jeu doré contre le code de production.

Le harnais vit à la racine du dépôt (`evals/`) mais importe le code applicatif
(`app.*`), qui vit dans `backend/`. Les deux racines sont donc ajoutées au
chemin d'import ici, une fois pour toutes : `make eval` fonctionne depuis
`backend/`, et `python evals/run.py` depuis la racine, sans variable
d'environnement à poser à la main.
"""

import sys
from pathlib import Path

_RACINE = Path(__file__).resolve().parents[1]

for _chemin in (_RACINE, _RACINE / "backend"):
    if str(_chemin) not in sys.path:
        sys.path.insert(0, str(_chemin))

DONNEES = _RACINE / "evals" / "data"
RAPPORTS = _RACINE / "evals" / "reports"
SEUILS = _RACINE / "evals" / "thresholds.yaml"
