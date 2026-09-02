"""Chiffrement des credentials d'intégration (Fernet - ADR-005).

La clé vient de `ENCRYPTION_KEY` (.env, jamais commitée). Les credentials ne
doivent JAMAIS apparaître en clair dans les logs : ne pas journaliser les
valeurs retournées par `decrypt_credentials`.
"""

import json

from cryptography.fernet import Fernet

from app.config import settings


def _fernet() -> Fernet:
    return Fernet(settings.ENCRYPTION_KEY.encode())


def encrypt_credentials(credentials: dict[str, str]) -> bytes:
    """Sérialise et chiffre un dictionnaire de credentials (stockage bytea)."""
    return _fernet().encrypt(json.dumps(credentials).encode())


def decrypt_credentials(token: bytes) -> dict[str, str]:
    """Déchiffre un bloc produit par `encrypt_credentials`."""
    data: dict[str, str] = json.loads(_fernet().decrypt(token))
    return data
