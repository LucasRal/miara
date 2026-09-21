"""Endpoints conversationnels de l'agent commercial (flux A).

Un tour de conversation = un appel de la boucle bornée de `core`, avec
l'historique relu en base et les nouveaux messages réécrits. Le contexte
d'agent est construit ICI, à partir du contexte de requête authentifié :
`org_id`, `user_id` et rôle ne viennent jamais du corps de la requête ni du
modèle (contrainte 2 de l'architecture).

Trois réponses possibles à un message, discriminées par `type` :
`final` (texte), `needs_confirmation` (écriture en attente, avec `preview`)
et `step_limit` (boucle arrêtée à max_steps).

Confirmation : `POST .../confirm/{call_id}` rejoue la boucle avec l'appel
autorisé. Le `trace_id` de ce rejeu est DÉTERMINISTE — uuid5(conversation,
call_id) — pour que deux clics sur « Confirmer » retombent sur la même clé
d'idempotence côté outils d'écriture et n'écrivent qu'une fois.

Le flux SSE diffuse les étapes de trace au fil de l'eau, puis le résultat.
"""

import asyncio
import json
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Annotated, Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.auth.deps import RequestContext as AuthContext
from app.auth.deps import require_role
from app.core.agents import (
    AgentResult,
    Final,
    NeedsConfirmation,
    RequestContext,
    load_history,
    run,
    save_messages,
)
from app.core.llm import LLMGateway, gateway_dependency
from app.core.models import AgentTrace, Conversation, Message
from app.sales.agents.assistant import AGENT_NAME, sales_assistant

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/sales", tags=["sales"])

# L'agent commercial est accessible aux rôles commerciaux et aux responsables.
SalesContext = Annotated[AuthContext, Depends(require_role("owner", "admin", "sales"))]


Gateway = Annotated[LLMGateway, Depends(gateway_dependency)]


class MessageIn(BaseModel):
    message: str = Field(min_length=1, max_length=4000)


def _agent_context(ctx: AuthContext, conversation_id: uuid.UUID, **kwargs: Any) -> RequestContext:
    return RequestContext(
        org_id=ctx.org_id,
        user_id=ctx.user_id,
        role=ctx.role.value,
        conversation_id=conversation_id,
        **kwargs,
    )


async def _require_conversation(ctx: AuthContext, conversation_id: uuid.UUID) -> Conversation:
    """404 si la conversation n'existe pas — ou appartient à une autre org
    (le RLS la rend simplement invisible)."""
    conversation = await ctx.session.get(Conversation, conversation_id)
    if conversation is None or conversation.agent != AGENT_NAME:
        raise HTTPException(status_code=404, detail="Conversation introuvable")
    return conversation


def _serialize(result: AgentResult, conversation_id: uuid.UUID) -> dict[str, Any]:
    common = {"conversation_id": str(conversation_id), "trace_id": str(result.trace_id)}
    if isinstance(result, Final):
        return {**common, "type": "final", "content": result.content}
    if isinstance(result, NeedsConfirmation):
        return {
            **common,
            "type": "needs_confirmation",
            "call_id": result.call_id,
            "tool": result.tool,
            "args": result.args,
            "preview": result.preview,
        }
    return {**common, "type": "step_limit", "steps": result.steps}


async def _turn(
    ctx: AuthContext,
    conversation_id: uuid.UUID,
    gateway: LLMGateway,
    *,
    input: str | None,
    confirmations: set[str] | None = None,
    trace_id: uuid.UUID | None = None,
    observer: Callable[[dict[str, Any]], None] | None = None,
) -> AgentResult:
    """Un tour : historique → boucle bornée → persistance des nouveaux messages."""
    extra: dict[str, Any] = {"trace_id": trace_id} if trace_id is not None else {}
    agent_ctx = _agent_context(ctx, conversation_id, **extra)
    history = await load_history(agent_ctx, conversation_id)
    result = await run(
        sales_assistant,
        input,
        agent_ctx,
        history=history,
        confirmations=confirmations,
        gateway=gateway,
        observer=observer,
    )
    if result.new_messages:
        await save_messages(agent_ctx, AGENT_NAME, result.new_messages, conversation_id)
    logger.info(
        "sales_turn",
        conversation_id=str(conversation_id),
        trace_id=str(result.trace_id),
        outcome=type(result).__name__,
    )
    return result


# --- endpoints -----------------------------------------------------------


@router.post("/conversations", status_code=201)
async def create_conversation(ctx: SalesContext) -> dict[str, Any]:
    conversation = Conversation(organization_id=ctx.org_id, agent=AGENT_NAME, user_id=ctx.user_id)
    ctx.session.add(conversation)
    await ctx.session.flush()
    return {"id": str(conversation.id), "agent": AGENT_NAME}


@router.post("/conversations/{conversation_id}/messages")
async def post_message(
    conversation_id: uuid.UUID, body: MessageIn, ctx: SalesContext, gateway: Gateway
) -> dict[str, Any]:
    await _require_conversation(ctx, conversation_id)
    result = await _turn(ctx, conversation_id, gateway, input=body.message)
    return _serialize(result, conversation_id)


@router.post("/conversations/{conversation_id}/confirm/{call_id}")
async def confirm_call(
    conversation_id: uuid.UUID, call_id: str, ctx: SalesContext, gateway: Gateway
) -> dict[str, Any]:
    """Autorise UN appel d'écriture en attente et poursuit la boucle."""
    await _require_conversation(ctx, conversation_id)
    result = await _turn(
        ctx,
        conversation_id,
        gateway,
        input=None,
        confirmations={call_id},
        trace_id=uuid.uuid5(conversation_id, call_id),
    )
    return _serialize(result, conversation_id)


@router.get("/conversations/{conversation_id}")
async def get_conversation(conversation_id: uuid.UUID, ctx: SalesContext) -> dict[str, Any]:
    """Messages de la conversation + trace d'exécution associée (chap. 8)."""
    conversation = await _require_conversation(ctx, conversation_id)
    messages = (
        (
            await ctx.session.execute(
                select(Message)
                .where(Message.conversation_id == conversation_id)
                .order_by(Message.position)
            )
        )
        .scalars()
        .all()
    )
    traces = (
        (
            await ctx.session.execute(
                select(AgentTrace)
                .where(AgentTrace.conversation_id == conversation_id)
                .order_by(AgentTrace.created_at, AgentTrace.step)
            )
        )
        .scalars()
        .all()
    )
    return {
        "id": str(conversation.id),
        "agent": conversation.agent,
        "created_at": conversation.created_at.isoformat(),
        "messages": [
            {
                "position": m.position,
                "role": m.role,
                "content": m.content,
                "tool_calls": m.tool_calls_json,
                "tool_call_id": m.tool_call_id,
            }
            for m in messages
        ],
        "trace": [
            {
                "trace_id": str(t.trace_id),
                "step": t.step,
                "kind": t.kind,
                "tool": t.tool,
                "summary": t.result_summary,
                "latency_ms": t.latency_ms,
            }
            for t in traces
        ],
    }


# --- streaming SSE -------------------------------------------------------


def _sse(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False, default=str)}\n\n"


async def _sse_stream(
    turn: Callable[..., Awaitable[AgentResult]], conversation_id: uuid.UUID
) -> AsyncIterator[str]:
    """Diffuse les étapes de trace au fil de l'eau, puis le résultat final.

    La boucle tourne dans une tâche ; l'observateur (synchrone) dépose ses
    événements dans une file que ce générateur vide.
    """
    queue: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue()

    async def runner() -> AgentResult:
        try:
            return await turn(observer=queue.put_nowait)
        finally:
            queue.put_nowait(None)  # sentinelle de fin, même en cas d'erreur

    task = asyncio.create_task(runner())
    while (event := await queue.get()) is not None:
        yield _sse("step", event)
    try:
        result = await task
    except Exception as exc:
        logger.exception("sales_stream_failed")
        yield _sse("error", {"type": "error", "detail": f"{type(exc).__name__}: {exc}"})
        return
    yield _sse("result", _serialize(result, conversation_id))


@router.post("/conversations/{conversation_id}/messages/stream")
async def post_message_stream(
    conversation_id: uuid.UUID, body: MessageIn, ctx: SalesContext, gateway: Gateway
) -> StreamingResponse:
    """Même tour que `POST .../messages`, en SSE : `step`* puis `result`."""
    await _require_conversation(ctx, conversation_id)

    async def turn(observer: Callable[[dict[str, Any]], None]) -> AgentResult:
        return await _turn(ctx, conversation_id, gateway, input=body.message, observer=observer)

    async def stream() -> AsyncIterator[str]:
        async for chunk in _sse_stream(turn, conversation_id):
            yield chunk

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
