"""Passerelle LLM unique (ADR-004, ADR-011).

Accepte un ALIAS (jamais un nom de modèle : config/llm.yaml est le seul
endroit où des modèles sont nommés), applique retries et replis via
litellm.Router, valide la sortie structurée (1 nouvelle tentative avec
l'erreur renvoyée au modèle), et journalise CHAQUE appel dans `llm_calls`
de façon asynchrone (fire-and-forget, `flush_logs()` pour attendre).

Règles :
- `org_id` vient du CallContext (requête / tâche Celery), jamais du LLM ;
- les logs applicatifs ne contiennent JAMAIS le contenu des messages —
  seulement des métadonnées (alias, agent, latence, statut).
"""

import asyncio
import json
import os
import time
import uuid
from collections.abc import Sequence
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Any, cast

import structlog
import yaml
from litellm import completion_cost
from litellm.router import Router
from pydantic import BaseModel, ValidationError

from app.config import settings
from app.core.models import LLMCall
from app.core.tenant import tenant_session

logger = structlog.get_logger(__name__)

_DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[3] / "config" / "llm.yaml"


class LLMError(Exception):
    """Erreur de la passerelle LLM."""


class UnknownAliasError(LLMError):
    """Alias absent de config/llm.yaml."""


class StructuredOutputError(LLMError):
    """Sortie JSON toujours invalide après la nouvelle tentative."""


@dataclass(frozen=True)
class CallContext:
    """Traçabilité d'un appel. `org_id` vient du contexte, jamais du LLM."""

    org_id: uuid.UUID
    agent: str
    prompt_version: int | None = None
    trace_id: uuid.UUID = field(default_factory=uuid.uuid4)


@dataclass
class LLMResult:
    content: str | None
    parsed: BaseModel | None
    tool_calls: list[dict[str, Any]] | None
    model_used: str
    input_tokens: int
    output_tokens: int
    latency_ms: int
    cost_usd: Decimal | None
    trace_id: uuid.UUID


def _normalize_model(alias_or_model: str | dict[str, Any]) -> dict[str, Any]:
    """`primary`/`fallbacks` acceptent un nom de modèle ou un mapping litellm_params."""
    if isinstance(alias_or_model, str):
        return {"model": alias_or_model}
    return dict(alias_or_model)


def _schema_instruction(response_model: type[BaseModel]) -> dict[str, str]:
    schema = json.dumps(response_model.model_json_schema(), ensure_ascii=False)
    return {
        "role": "user",
        "content": (
            "Réponds UNIQUEMENT avec un objet JSON valide conforme à ce schéma "
            "JSON, sans texte autour ni bloc de code :\n" + schema
        ),
    }


def _parse_structured(response_model: type[BaseModel], content: str | None) -> BaseModel:
    if not content:
        raise ValueError("réponse vide")
    text = content.strip()
    if text.startswith("```"):  # tolère un bloc de code malgré la consigne
        text = text.split("\n", 1)[1] if "\n" in text else ""
        text = text.rsplit("```", 1)[0]
    data = json.loads(text)
    return response_model.model_validate(data)


class LLMGateway:
    def __init__(self, config: dict[str, Any] | None = None) -> None:
        if config is None:
            path = (
                Path(settings.LLM_CONFIG_PATH) if settings.LLM_CONFIG_PATH else _DEFAULT_CONFIG_PATH
            )
            config = yaml.safe_load(path.read_text(encoding="utf-8"))
        # litellm lit les clés fournisseurs dans l'environnement.
        for key in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY"):
            value = getattr(settings, key)
            if value:
                os.environ.setdefault(key, value)

        defaults: dict[str, Any] = config.get("defaults", {})
        timeout = defaults.get("timeout", 30)
        aliases: dict[str, dict[str, Any]] = config["aliases"]
        self._aliases = set(aliases)

        model_list: list[dict[str, Any]] = []
        fallbacks: list[dict[str, list[str]]] = []
        for alias, spec in aliases.items():
            primary = _normalize_model(spec["primary"])
            primary.setdefault("timeout", spec.get("timeout", timeout))
            model_list.append({"model_name": alias, "litellm_params": primary})
            names: list[str] = []
            for i, fb in enumerate(spec.get("fallbacks", [])):
                fb_params = _normalize_model(fb)
                fb_params.setdefault("timeout", spec.get("timeout", timeout))
                name = f"{alias}:fallback{i}"
                model_list.append({"model_name": name, "litellm_params": fb_params})
                names.append(name)
            if names:
                fallbacks.append({alias: names})

        self._router = Router(
            model_list=model_list,
            fallbacks=fallbacks,
            num_retries=defaults.get("max_retries", 2),
        )
        self._pending_logs: set[asyncio.Task[None]] = set()

    async def complete(
        self,
        alias: str,
        messages: Sequence[dict[str, Any]],
        *,
        ctx: CallContext,
        tools: list[dict[str, Any]] | None = None,
        response_model: type[BaseModel] | None = None,
    ) -> LLMResult:
        """Un appel LLM par alias. Avec `response_model` : JSON parsé et revalidé,
        1 nouvelle tentative (l'erreur est renvoyée au modèle), sinon
        `StructuredOutputError`. Chaque appel réseau = une ligne `llm_calls`."""
        if alias not in self._aliases:
            raise UnknownAliasError(f"Alias inconnu : {alias!r} (voir config/llm.yaml)")

        msgs = [dict(m) for m in messages]
        if response_model is not None:
            msgs.append(_schema_instruction(response_model))

        result = await self._invoke(alias, msgs, tools, ctx)
        # La validation structurée ne s'applique qu'aux réponses FINALES :
        # une réponse à base de tool_calls n'a pas (encore) de JSON à valider.
        if response_model is None or result.tool_calls:
            return result

        try:
            result.parsed = _parse_structured(response_model, result.content)
            return result
        except (ValueError, ValidationError) as first_error:
            retry_msgs = [
                *msgs,
                {"role": "assistant", "content": result.content or ""},
                {
                    "role": "user",
                    "content": (
                        f"Ta réponse n'est pas un JSON valide pour le schéma ({first_error}). "
                        "Renvoie UNIQUEMENT l'objet JSON corrigé."
                    ),
                },
            ]
            result = await self._invoke(alias, retry_msgs, tools, ctx)
            try:
                result.parsed = _parse_structured(response_model, result.content)
                return result
            except (ValueError, ValidationError) as second_error:
                raise StructuredOutputError(
                    f"Sortie non conforme après nouvelle tentative : {second_error}"
                ) from second_error

    async def _invoke(
        self,
        alias: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
        ctx: CallContext,
    ) -> LLMResult:
        start = time.perf_counter()
        try:
            response = await self._router.acompletion(
                model=alias, messages=cast(Any, messages), tools=tools
            )
        except Exception as exc:
            latency_ms = int((time.perf_counter() - start) * 1000)
            self._schedule_log(
                ctx,
                alias,
                model_used="",
                input_tokens=0,
                output_tokens=0,
                latency_ms=latency_ms,
                cost_usd=None,
                tool_calls=None,
                status="error",
                error=f"{type(exc).__name__}: {exc}",
            )
            logger.warning("llm_call_failed", alias=alias, agent=ctx.agent, latency_ms=latency_ms)
            raise
        latency_ms = int((time.perf_counter() - start) * 1000)

        message = response.choices[0].message
        raw_tool_calls = getattr(message, "tool_calls", None)
        tool_calls: list[dict[str, Any]] | None = None
        if raw_tool_calls:
            tool_calls = [
                {"id": tc.id, "name": tc.function.name, "arguments": tc.function.arguments}
                for tc in raw_tool_calls
            ]
        usage = getattr(response, "usage", None)
        try:
            cost = Decimal(str(round(completion_cost(completion_response=response), 6)))
        except Exception:  # modèle absent de la table de prix litellm
            cost = None

        result = LLMResult(
            content=message.content,
            parsed=None,
            tool_calls=tool_calls,
            model_used=str(response.model or ""),
            input_tokens=getattr(usage, "prompt_tokens", 0) or 0,
            output_tokens=getattr(usage, "completion_tokens", 0) or 0,
            latency_ms=latency_ms,
            cost_usd=cost,
            trace_id=ctx.trace_id,
        )
        self._schedule_log(
            ctx,
            alias,
            model_used=result.model_used,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            latency_ms=latency_ms,
            cost_usd=cost,
            tool_calls=tool_calls,
            status="ok",
            error=None,
        )
        logger.info(
            "llm_call",
            alias=alias,
            agent=ctx.agent,
            model_used=result.model_used,
            latency_ms=latency_ms,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
        )
        return result

    def _schedule_log(
        self,
        ctx: CallContext,
        alias: str,
        *,
        model_used: str,
        input_tokens: int,
        output_tokens: int,
        latency_ms: int,
        cost_usd: Decimal | None,
        tool_calls: list[dict[str, Any]] | None,
        status: str,
        error: str | None,
    ) -> None:
        """Journalisation asynchrone : ne bloque jamais la réponse à l'appelant."""
        task = asyncio.create_task(
            self._write_log(
                ctx,
                alias,
                model_used=model_used,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                latency_ms=latency_ms,
                cost_usd=cost_usd,
                tool_calls=tool_calls,
                status=status,
                error=error,
            )
        )
        self._pending_logs.add(task)
        task.add_done_callback(self._pending_logs.discard)

    async def _write_log(
        self,
        ctx: CallContext,
        alias: str,
        *,
        model_used: str,
        input_tokens: int,
        output_tokens: int,
        latency_ms: int,
        cost_usd: Decimal | None,
        tool_calls: list[dict[str, Any]] | None,
        status: str,
        error: str | None,
    ) -> None:
        try:
            async with tenant_session(ctx.org_id) as session:
                session.add(
                    LLMCall(
                        organization_id=ctx.org_id,
                        trace_id=ctx.trace_id,
                        agent=ctx.agent,
                        alias=alias,
                        model_used=model_used,
                        prompt_version=ctx.prompt_version,
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                        latency_ms=latency_ms,
                        cost_usd=cost_usd,
                        tool_calls_json=tool_calls,
                        status=status,
                        error=error,
                    )
                )
        except Exception:
            # Jamais le contenu des messages ; l'échec de journalisation ne doit
            # pas faire échouer l'appel métier.
            logger.exception("llm_call_log_failed", alias=alias, trace_id=str(ctx.trace_id))

    async def flush_logs(self) -> None:
        """Attend les journalisations en cours (tests, arrêt propre)."""
        if self._pending_logs:
            await asyncio.gather(*self._pending_logs, return_exceptions=True)


_gateway: LLMGateway | None = None


def get_gateway() -> LLMGateway:
    """Singleton paresseux : construit le Router à la première utilisation."""
    global _gateway
    if _gateway is None:
        _gateway = LLMGateway()
    return _gateway
