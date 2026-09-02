"""Tables transverses du socle.

`Integration` : connexion d'une organisation à un fournisseur externe
(Salesforce en premier - ADR-005). Première table métier : elle utilise le
mixin TenantScoped, comme toute table métier future. Les credentials sont
chiffrés (Fernet, app.core.crypto) - jamais en clair en base ni dans les logs.
"""

import uuid

from sqlalchemy import LargeBinary, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, TenantScoped


class Integration(TenantScoped, Base):
    __tablename__ = "integrations"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    provider: Mapped[str] = mapped_column(String(50))
    encrypted_credentials: Mapped[bytes] = mapped_column(LargeBinary)
    instance_url: Mapped[str | None] = mapped_column(String(500))
