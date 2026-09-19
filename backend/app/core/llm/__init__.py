"""Passerelle LLM (ADR-004) : point d'entrée unique vers les modèles.

Aucun module ne doit importer `litellm` directement — tout passe par
`app.core.llm.gateway.LLMGateway`.
"""

from app.core.llm.gateway import (
    CallContext,
    LLMGateway,
    LLMResult,
    StructuredOutputError,
    UnknownAliasError,
    get_gateway,
)
from app.core.llm.prompts import load_prompt

__all__ = [
    "CallContext",
    "LLMGateway",
    "LLMResult",
    "StructuredOutputError",
    "UnknownAliasError",
    "get_gateway",
    "load_prompt",
]
