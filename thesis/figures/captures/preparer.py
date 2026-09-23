"""Prepare un compte de lecture seule pour les captures d'ecran du memoire.

Le memoire illustre des ecrans remplis par des donnees REELLES, produites par
l'application elle-meme au fil des cartes precedentes. Plutot que de fabriquer
un jeu de demonstration pour la photo, ce script se contente de donner a un
compte dedie l'acces a une organisation existante :

1. inscription du compte par l'API publique `POST /auth/register` (rejouable :
   un 409 signifie qu'il existe deja) ;
2. insertion de la membership correspondante, avec le role `admin`, par la
   connexion d'administration de la base, la seule qui contourne le RLS.

C'est la SEULE ecriture faite par l'outillage de captures, et elle est
idempotente. Aucun mot de passe n'est ecrit dans le depot : il vient de la
variable d'environnement CAPTURES_PASSWORD.

    cd backend && CAPTURES_PASSWORD='...' uv run python \\
        ../thesis/figures/captures/preparer.py [slug-de-l-organisation]
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(RACINE / "backend"))

import httpx  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.ext.asyncio import create_async_engine  # noqa: E402

from app.config import settings  # noqa: E402

API = os.environ.get("CAPTURES_API", "http://127.0.0.1:8010/api/v1")
EMAIL = os.environ.get("CAPTURES_EMAIL", "captures-memoire@test.miara.dev")
SLUG = sys.argv[1] if len(sys.argv) > 1 else "lucas-corp"


async def main() -> int:
    mot_de_passe = os.environ.get("CAPTURES_PASSWORD")
    if not mot_de_passe:
        print("CAPTURES_PASSWORD absent de l'environnement", file=sys.stderr)
        return 1

    async with httpx.AsyncClient(timeout=20) as client:
        reponse = await client.post(
            f"{API}/auth/register",
            json={"email": EMAIL, "password": mot_de_passe, "full_name": "Captures memoire"},
        )
    if reponse.status_code not in (201, 409):
        print(f"inscription refusee : {reponse.status_code} {reponse.text}", file=sys.stderr)
        return 1

    moteur = create_async_engine(settings.DATABASE_URL_ADMIN)
    async with moteur.begin() as connexion:
        org = (
            await connexion.execute(
                text("SELECT id FROM organizations WHERE slug = :slug"), {"slug": SLUG}
            )
        ).scalar_one_or_none()
        if org is None:
            print(f"organisation inconnue : {SLUG}", file=sys.stderr)
            return 1
        utilisateur = (
            await connexion.execute(
                text("SELECT id FROM users WHERE email = :email"), {"email": EMAIL}
            )
        ).scalar_one()
        await connexion.execute(
            text(
                "INSERT INTO memberships (user_id, organization_id, role) "
                "VALUES (:u, :o, 'admin') ON CONFLICT DO NOTHING"
            ),
            {"u": utilisateur, "o": org},
        )
    await moteur.dispose()
    print(f"compte {EMAIL} membre admin de {SLUG}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
