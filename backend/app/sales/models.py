"""Tables du module sales.

`CrmWrite` : piste d'audit des écritures CRM faites par un agent (ADR-009).
Une ligne par tentative d'écriture confirmée — succès (avec `sf_record_id`) ou
échec (`status='error'`, `error` renseigné). Sert la figure « cycle de
confirmation humaine » du mémoire (chap. 5) et la mesure du temps commercial
économisé (chap. 8, H2).

`CoachingSession` : une évaluation du coach commercial. Les notes par critère
sont conservées pour suivre la progression d'un commercial dans le temps
(chap. 8 : accord IA/humain, courbe de progression).
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, TenantScoped


class CrmWrite(TenantScoped, Base):
    __tablename__ = "crm_writes"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    # Regroupe les écritures d'une même exécution d'agent.
    trace_id: Mapped[uuid.UUID] = mapped_column(index=True)
    tool: Mapped[str] = mapped_column(String(100))
    args_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    # Id de l'enregistrement Salesforce créé/modifié (None si l'écriture a échoué).
    sf_record_id: Mapped[str | None] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(20))  # created | error
    # Utilisateur ayant confirmé l'écriture (contexte de requête, jamais le LLM).
    confirmed_by: Mapped[uuid.UUID | None] = mapped_column(index=True)
    error: Mapped[str | None] = mapped_column(Text())
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )


class CoachingSession(TenantScoped, Base):
    __tablename__ = "coaching_sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    # Commercial évalué : c'est SA progression que la table suit.
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    trace_id: Mapped[uuid.UUID] = mapped_column(index=True)
    kind: Mapped[str] = mapped_column(String(20))  # call_note | email | script
    # Enregistrement Salesforce concerné (compte ou opportunité), si fourni.
    record_id: Mapped[str | None] = mapped_column(String(50))
    source_text: Mapped[str] = mapped_column(Text())
    overall_0_100: Mapped[int]
    # {critère: note} — dénormalisé pour les moyennes de progression.
    scores_json: Mapped[dict[str, Any]] = mapped_column(JSONB)
    feedback_json: Mapped[dict[str, Any]] = mapped_column(JSONB)
    prompt_version: Mapped[int | None]
    # Écriture CRM proposée par la plateforme, en attente de confirmation.
    pending_write_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    sf_task_id: Mapped[str | None] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
