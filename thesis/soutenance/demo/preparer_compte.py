"""Prépare le compte utilisé par la démonstration de soutenance.

Le principe est celui déjà retenu pour les captures du mémoire
(`thesis/figures/captures/preparer.py`) : on ne fabrique pas un jeu de
démonstration pour la photo, on donne à un compte dédié l'accès à une
organisation existante, celle qui porte la connexion Salesforce réelle.

1. inscription du compte par l'API publique `POST /auth/register` (rejouable :
   un 409 signifie qu'il existe déjà) ;
2. insertion de la membership `admin` par la connexion d'administration de la
   base, la seule qui contourne le RLS.

Aucun mot de passe dans le dépôt : il vient de `DEMO_PASSWORD` (fichier
`thesis/soutenance/demo/.env.local`, ignoré par git).

    cd backend && set -a && . ../thesis/soutenance/demo/.env.local && set +a \\
        && uv run python ../thesis/soutenance/demo/preparer_compte.py
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

def _charger_env_local() -> None:
    """Lit `thesis/soutenance/demo/.env.local` (ignoré par git) s'il existe.

    Le mot de passe ne transite ainsi ni par la ligne de commande ni par le
    dépôt : il reste dans un fichier local à permissions restreintes.
    """
    fichier = Path(__file__).resolve().parent / ".env.local"
    if not fichier.exists():
        return
    for ligne in fichier.read_text(encoding="utf-8").splitlines():
        ligne = ligne.strip()
        if not ligne or ligne.startswith("#") or "=" not in ligne:
            continue
        cle, valeur = ligne.split("=", 1)
        os.environ.setdefault(cle.strip(), valeur.strip())


_charger_env_local()

API = os.environ.get("DEMO_API", "http://127.0.0.1:8010/api/v1")
EMAIL = os.environ.get("DEMO_EMAIL", "demo-soutenance@test.miara.dev")
SLUG = os.environ.get("DEMO_ORG_SLUG", "lucas-corp")


async def main() -> int:
    mot_de_passe = os.environ.get("DEMO_PASSWORD")
    if not mot_de_passe:
        print("DEMO_PASSWORD absent de l'environnement", file=sys.stderr)
        return 1

    async with httpx.AsyncClient(timeout=20) as client:
        reponse = await client.post(
            f"{API}/auth/register",
            json={"email": EMAIL, "password": mot_de_passe, "full_name": "Démonstration"},
        )
    if reponse.status_code not in (201, 409):
        print(f"inscription refusée : {reponse.status_code} {reponse.text}", file=sys.stderr)
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
