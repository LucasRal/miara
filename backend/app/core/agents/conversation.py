"""Historique persisté : tables `conversations` / `messages` (format OpenAI).

Le runtime reste pur (il reçoit `history`, renvoie `new_messages`) ; ces
helpers font le pont avec la BDD, sous RLS via tenant_session.
"""

import uuid
from typing import Any

from sqlalchemy import func, select

from app.core.agents.context import RequestContext
from app.core.models import Conversation, Message
from app.core.tenant import tenant_session


async def save_messages(
    ctx: RequestContext,
    agent: str,
    new_messages: list[dict[str, Any]],
    conversation_id: uuid.UUID | None = None,
) -> uuid.UUID:
    """Ajoute les messages à la conversation (créée si besoin). Retourne son id."""
    async with tenant_session(ctx.org_id, ctx.user_id) as session:
        if conversation_id is None:
            conversation = Conversation(
                organization_id=ctx.org_id, agent=agent, user_id=ctx.user_id
            )
            session.add(conversation)
            await session.flush()
            conversation_id = conversation.id
            next_position = 0
        else:
            next_position = (
                await session.execute(
                    select(func.coalesce(func.max(Message.position) + 1, 0)).where(
                        Message.conversation_id == conversation_id
                    )
                )
            ).scalar_one()

        for offset, msg in enumerate(new_messages):
            session.add(
                Message(
                    organization_id=ctx.org_id,
                    conversation_id=conversation_id,
                    position=next_position + offset,
                    role=msg["role"],
                    content=msg.get("content"),
                    tool_calls_json=msg.get("tool_calls"),
                    tool_call_id=msg.get("tool_call_id"),
                )
            )
    return conversation_id


async def load_history(ctx: RequestContext, conversation_id: uuid.UUID) -> list[dict[str, Any]]:
    """Reconstruit l'historique (format OpenAI) dans l'ordre des positions."""
    async with tenant_session(ctx.org_id, ctx.user_id) as session:
        rows = (
            (
                await session.execute(
                    select(Message)
                    .where(Message.conversation_id == conversation_id)
                    .order_by(Message.position)
                )
            )
            .scalars()
            .all()
        )
    history: list[dict[str, Any]] = []
    for row in rows:
        msg: dict[str, Any] = {"role": row.role, "content": row.content}
        if row.tool_calls_json is not None:
            msg["tool_calls"] = row.tool_calls_json
        if row.tool_call_id is not None:
            msg["tool_call_id"] = row.tool_call_id
        history.append(msg)
    return history
