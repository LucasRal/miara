"""Boucle d'agent bornée — le cœur du mémoire (chap. 5), sans framework.

Déroulé : appel LLM → si tool_calls : valider les arguments (Pydantic),
demander confirmation pour les écritures (ADR-009), exécuter, réinjecter les
résultats, continuer → sinon réponse finale. Au plus `max_steps` appels LLM,
puis `StepLimitExceeded`.

Résultat = union typée `Final | NeedsConfirmation | StepLimitExceeded` — pas
d'exception pour les issues normales du flux.

Reprise après confirmation : l'appelant repasse l'historique (qui se termine
par le message assistant contenant l'appel d'écriture en attente) avec
`confirmations={call_id}` ; la boucle exécute alors l'outil UNE SEULE FOIS,
sans rappeler le LLM pour re-décider.

Chaque événement est tracé dans `agent_traces` (flush en fin de run, même en
cas d'erreur) ; les résumés y sont tronqués et les logs applicatifs ne
contiennent jamais le contenu des messages. Un `observer` optionnel reçoit ces
mêmes événements à chaud (diffusion SSE de la progression).

Deux modèles par agent (ADR-011) : le 1er appel part sur `model_alias` (léger,
il choisit les outils), les suivants sur `synthesis_alias` s'il est défini
(fort, il rédige à partir des résultats d'outils).
"""

import json
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from typing import Any

import structlog
from pydantic import ValidationError

from app.core.agents.context import RequestContext
from app.core.agents.definition import AgentDefinition
from app.core.agents.tool import Tool
from app.core.llm import CallContext, LLMGateway, get_gateway, load_prompt
from app.core.models import AgentTrace
from app.core.tenant import tenant_session

logger = structlog.get_logger(__name__)

_SUMMARY_MAX = 500

# Observateur d'étapes : appelé À CHAUD à chaque événement tracé, pour diffuser
# la progression (SSE) sans attendre le flush final. Synchrone et non bloquant
# — il ne doit jamais ralentir ni faire échouer la boucle.
StepObserver = Callable[[dict[str, Any]], None]


@dataclass
class Final:
    content: str | None
    trace_id: uuid.UUID
    structured: Any | None = None  # instance de output_schema si défini
    new_messages: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class NeedsConfirmation:
    """Écriture en attente de validation humaine (ADR-009). `args` est montré
    à l'utilisateur ; la relance se fait avec confirmations={call_id}."""

    call_id: str
    tool: str
    args: dict[str, Any]
    trace_id: uuid.UUID
    preview: str | None = None  # phrase de confirmation lisible (ADR-009)
    new_messages: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class StepLimitExceeded:
    trace_id: uuid.UUID
    steps: int
    new_messages: list[dict[str, Any]] = field(default_factory=list)


AgentResult = Final | NeedsConfirmation | StepLimitExceeded


class _Tracer:
    """Accumule les événements puis les écrit en une transaction (finally)."""

    def __init__(self, ctx: RequestContext, observer: StepObserver | None = None) -> None:
        self._ctx = ctx
        self._observer = observer
        self._step = 0
        self._rows: list[AgentTrace] = []

    def add(
        self,
        kind: str,
        *,
        tool: str | None = None,
        args: dict[str, Any] | None = None,
        summary: str | None = None,
        latency_ms: int | None = None,
    ) -> None:
        self._step += 1
        summary = summary[:_SUMMARY_MAX] if summary else None
        self._rows.append(
            AgentTrace(
                organization_id=self._ctx.org_id,
                trace_id=self._ctx.trace_id,
                conversation_id=self._ctx.conversation_id,
                step=self._step,
                kind=kind,
                tool=tool,
                args_json=args,
                result_summary=summary,
                latency_ms=latency_ms,
            )
        )
        if self._observer is not None:
            event = {
                "step": self._step,
                "kind": kind,
                "tool": tool,
                "summary": summary,
                "latency_ms": latency_ms,
            }
            try:
                self._observer(event)
            except Exception:  # un consommateur défaillant n'interrompt pas l'agent
                logger.warning("agent_step_observer_failed", kind=kind)

    async def flush(self) -> None:
        if not self._rows:
            return
        try:
            async with tenant_session(self._ctx.org_id, self._ctx.user_id) as session:
                session.add_all(self._rows)
        except Exception:
            logger.exception("agent_trace_flush_failed", trace_id=str(self._ctx.trace_id))
        self._rows = []


def _assistant_message(content: str | None, tool_calls: list[dict[str, Any]]) -> dict[str, Any]:
    """Message assistant au format OpenAI, rejouable tel quel vers le LLM."""
    return {
        "role": "assistant",
        "content": content,
        "tool_calls": [
            {
                "id": c["id"],
                "type": "function",
                "function": {"name": c["name"], "arguments": c["arguments"]},
            }
            for c in tool_calls
        ],
    }


_NON_CONFIRME = "Action non confirmée par l'utilisateur : elle n'a pas été exécutée."


def _pending_tool_calls(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Appels d'outils du dernier message assistant restés sans résultat
    (cas d'une reprise après NeedsConfirmation)."""
    last_calls: list[dict[str, Any]] = []
    answered: set[str] = set()
    for msg in messages:
        if msg.get("role") == "assistant" and msg.get("tool_calls"):
            last_calls = [
                {
                    "id": c["id"],
                    "name": c["function"]["name"],
                    "arguments": c["function"]["arguments"],
                }
                for c in msg["tool_calls"]
            ]
            answered = set()
        elif msg.get("role") == "tool":
            answered.add(str(msg.get("tool_call_id")))
    return [c for c in last_calls if c["id"] not in answered]


async def _handle_tool_calls(
    calls: list[dict[str, Any]],
    tools_by_name: dict[str, Tool],
    confirmations: set[str],
    ctx: RequestContext,
    messages: list[dict[str, Any]],
    new_messages: list[dict[str, Any]],
    tracer: _Tracer,
) -> NeedsConfirmation | None:
    """Valide et exécute les appels d'outils ; s'arrête sur une écriture non
    confirmée. Toute erreur (outil inconnu, args invalides, échec d'exécution)
    est renvoyée AU MODÈLE comme résultat d'outil — jamais d'exécution avec
    des arguments invalides."""

    def tool_result(call_id: str, payload: str) -> None:
        msg = {"role": "tool", "tool_call_id": call_id, "content": payload}
        messages.append(msg)
        new_messages.append(msg)

    for call in calls:
        tool = tools_by_name.get(call["name"])
        if tool is None:
            tracer.add("tool_error", tool=call["name"], summary="outil inconnu")
            tool_result(call["id"], f"Erreur : outil inconnu {call['name']!r}.")
            continue

        try:
            args = tool.args_schema.model_validate_json(call["arguments"] or "{}")
        except ValidationError as exc:
            tracer.add("tool_error", tool=tool.name, summary=f"args invalides : {exc}")
            tool_result(call["id"], f"Arguments invalides pour {tool.name} : {exc}")
            continue  # PAS d'exécution

        if tool.is_write and call["id"] not in confirmations:
            args_dict = args.model_dump()
            tracer.add("needs_confirmation", tool=tool.name, args=args_dict)
            return NeedsConfirmation(
                call_id=call["id"],
                tool=tool.name,
                args=args_dict,
                trace_id=ctx.trace_id,
                preview=await tool.render_preview(args, ctx),
            )

        start = time.perf_counter()
        try:
            # call_id posé dans le contexte : clé d'idempotence des écritures.
            result = await tool.run(args, replace(ctx, call_id=call["id"]))
        except Exception as exc:
            latency = int((time.perf_counter() - start) * 1000)
            tracer.add(
                "tool_error",
                tool=tool.name,
                summary=f"{type(exc).__name__}: {exc}",
                latency_ms=latency,
            )
            tool_result(call["id"], f"Erreur pendant {tool.name} : {exc}")
            continue
        latency = int((time.perf_counter() - start) * 1000)
        payload = json.dumps(result, ensure_ascii=False, default=str)
        tracer.add(
            "tool_exec",
            tool=tool.name,
            args=args.model_dump(),
            summary=payload,
            latency_ms=latency,
        )
        tool_result(call["id"], payload)
    return None


async def run(
    definition: AgentDefinition,
    input: str | None,
    ctx: RequestContext,
    history: list[dict[str, Any]] | None = None,
    confirmations: set[str] | None = None,
    gateway: LLMGateway | None = None,
    observer: StepObserver | None = None,
) -> AgentResult:
    gateway = gateway or get_gateway()
    confirmations = confirmations or set()
    prompt_text, prompt_version = load_prompt(definition.prompt_name)

    messages: list[dict[str, Any]] = [{"role": "system", "content": prompt_text}]
    messages += [dict(m) for m in history or []]
    new_messages: list[dict[str, Any]] = []
    tools_by_name = {t.name: t for t in definition.tools}
    tool_schemas = [t.to_llm_schema() for t in definition.tools] or None
    tracer = _Tracer(ctx, observer)

    if input is not None:
        # Un tour précédent a pu s'arrêter sur une confirmation jamais donnée
        # (l'humain refuse, ou ferme l'onglet). L'appel d'outil reste alors sans
        # résultat dans l'historique. On le clôt AVANT d'ouvrir le nouveau tour,
        # pour deux raisons : l'API refuse un message assistant porteur de
        # tool_calls suivi d'autre chose que ses résultats, et sans cela
        # l'action écartée serait rejouée au tour suivant. Le refus est
        # persisté : c'est une décision humaine, elle appartient à la trace
        # d'audit (ADR-009).
        for call in _pending_tool_calls(messages):
            if call["id"] in confirmations:
                continue
            refus = {"role": "tool", "tool_call_id": call["id"], "content": _NON_CONFIRME}
            messages.append(refus)
            new_messages.append(refus)
            tracer.add("refused", tool=call["name"], summary=_NON_CONFIRME)

        user_msg = {"role": "user", "content": input}
        messages.append(user_msg)
        new_messages.append(user_msg)

    llm_steps = 0
    has_tool_results = False

    try:
        # Reprise : appels d'outils en attente dans l'historique (confirmation).
        pending = _pending_tool_calls(messages)
        while True:
            if pending:
                blocked = await _handle_tool_calls(
                    pending, tools_by_name, confirmations, ctx, messages, new_messages, tracer
                )
                if blocked is not None:
                    blocked.new_messages = new_messages
                    return blocked
                pending = []
                has_tool_results = True
                continue

            if llm_steps >= definition.max_steps:
                tracer.add("step_limit", summary=f"{llm_steps} appels LLM")
                return StepLimitExceeded(
                    trace_id=ctx.trace_id, steps=llm_steps, new_messages=new_messages
                )
            # Escalade déterministe : routage sur l'alias léger, synthèse sur
            # l'alias fort une fois les résultats d'outils en main (ADR-011).
            alias = definition.alias_for_step(has_tool_results)
            llm_steps += 1
            result = await gateway.complete(
                alias,
                messages,
                ctx=CallContext(
                    org_id=ctx.org_id,
                    agent=definition.name,
                    prompt_version=prompt_version,
                    trace_id=ctx.trace_id,
                ),
                tools=tool_schemas,
                response_model=definition.output_schema,
            )
            tracer.add(
                "llm_call",
                summary=f"alias={alias} model={result.model_used} "
                f"tool_calls={len(result.tool_calls or [])}",
                latency_ms=result.latency_ms,
            )

            if not result.tool_calls:
                final_msg = {"role": "assistant", "content": result.content}
                messages.append(final_msg)
                new_messages.append(final_msg)
                tracer.add("final", summary=result.content)
                return Final(
                    content=result.content,
                    trace_id=ctx.trace_id,
                    structured=result.parsed,
                    new_messages=new_messages,
                )

            assistant_msg = _assistant_message(result.content, result.tool_calls)
            messages.append(assistant_msg)
            new_messages.append(assistant_msg)
            pending = [dict(c) for c in result.tool_calls]
    finally:
        await tracer.flush()
