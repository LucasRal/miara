"""Agents du module commercial (définitions déclaratives, runtime dans core)."""

from app.sales.agents.assistant import sales_assistant
from app.sales.agents.coach import CoachingFeedback, sales_coach

__all__ = ["CoachingFeedback", "sales_assistant", "sales_coach"]
