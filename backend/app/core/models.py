"""Tables transverses du socle.

`Integration` : connexion d'une organisation à un fournisseur externe
(Salesforce en premier - ADR-005). Première table métier : elle utilise le
mixin TenantScoped, comme toute table métier future. Les credentials sont
chiffrés (Fernet, app.core.crypto) - jamais en clair en base ni dans les logs.

`LLMCall` : journal de chaque appel LLM (ADR-004) - source des tableaux
coût/latence par alias et par organisation du mémoire (chap. 8).

`AgentTrace` / `Conversation` / `Message` : traçabilité et historique du
runtime d'agent (carte runtime, chap. 5 et 8 du mémoire).
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import DateTime, ForeignKey, LargeBinary, Numeric, String, Text, text
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


class AgentTrace(TenantScoped, Base):
    """Un événement de la boucle d'agent (appel LLM, outil, arrêt) par étape."""

    __tablename__ = "agent_traces"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    trace_id: Mapped[uuid.UUID] = mapped_column(index=True)
    # Conversation d'origine (None : agent lancé hors conversation, ex. Celery).
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), index=True, nullable=True
    )
    step: Mapped[int]
    # llm_call | tool_exec | tool_error | needs_confirmation | final | step_limit
    kind: Mapped[str] = mapped_column(String(30))
    tool: Mapped[str | None] = mapped_column(String(100))
    args_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    result_summary: Mapped[str | None] = mapped_column(Text())
    latency_ms: Mapped[int | None]
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )


class Conversation(TenantScoped, Base):
    __tablename__ = "conversations"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    agent: Mapped[str] = mapped_column(String(100))
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )


class Message(TenantScoped, Base):
    """Message d'historique au format OpenAI (rôle, contenu, tool_calls)."""

    __tablename__ = "messages"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), index=True
    )
    position: Mapped[int]
    role: Mapped[str] = mapped_column(String(20))
    content: Mapped[str | None] = mapped_column(Text())
    tool_calls_json: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB, nullable=True)
    tool_call_id: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
