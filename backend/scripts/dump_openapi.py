"""Écrit le schéma OpenAPI de l'API sur la sortie standard.

Sert à générer les types TypeScript du frontend (`make types`) sans avoir à
démarrer un serveur : le contrat HTTP vient du code, jamais d'une copie tenue
à jour à la main.
"""

import json

import app.db_registry  # noqa: F401  (enregistre les tables avant l'import des routers)
from app.main import app


def main() -> None:
    print(json.dumps(app.openapi(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
