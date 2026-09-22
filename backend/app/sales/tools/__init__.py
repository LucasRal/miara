"""Outils d'agent du module sales (ADR-008, ADR-009)."""

from app.sales.tools.read import (
    READ_TOOLS,
    find_account,
    find_contact,
    get_account_context,
    get_opportunity,
    search_activities,
)
from app.sales.tools.write import (
    WRITE_TOOLS,
    create_account,
    create_contact,
    create_opportunity,
    create_task,
    log_call_note,
    update_opportunity_stage,
)

__all__ = [
    "READ_TOOLS",
    "WRITE_TOOLS",
    "create_account",
    "create_contact",
    "create_opportunity",
    "create_task",
    "find_account",
    "find_contact",
    "get_account_context",
    "get_opportunity",
    "log_call_note",
    "search_activities",
    "update_opportunity_stage",
]
