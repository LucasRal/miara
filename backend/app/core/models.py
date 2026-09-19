"""Tables transverses du socle.

`Integration` : connexion d'une organisation à un fournisseur externe
(Salesforce en premier - ADR-005). Première table métier : elle utilise le
mixin TenantScoped, comme toute table métier future. Les credentials sont
chiffrés (Fernet, app.core.crypto) - jamais en clair en base ni dans les logs.

`LLMCall` : journal de chaque appel LLM (ADR-004) - source des tableaux
coût/latence par alias et par organisation du mémoire (chap. 8).
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import DateTime, LargeBinary, Numeric, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
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


class LLMCall(TenantScoped, Base):
    __tablename__ = "llm_calls"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    # Regroupe les appels d'une même exécution d'agent (boucle, retries JSON).
    trace_id: Mapped[uuid.UUID] = mapped_column(index=True)
    agent: Mapped[str] = mapped_column(String(100))
    alias: Mapped[str] = mapped_column(String(100))
    # Modèle réellement servi (peut différer du primaire si repli).
    model_used: Mapped[str] = mapped_column(String(200))
    prompt_version: Mapped[int | None]
    input_tokens: Mapped[int] = mapped_column(default=0)
    output_tokens: Mapped[int] = mapped_column(default=0)
    latency_ms: Mapped[int]
    # None si le coût est inconnu de litellm (modèle hors table des prix).
    cost_usd: Mapped[Decimal | None] = mapped_column(Numeric(12, 6))
    tool_calls_json: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(String(20))
    error: Mapped[str | None] = mapped_column(Text())
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )

