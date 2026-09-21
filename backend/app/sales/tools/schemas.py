"""Modèles compacts renvoyés par les outils de lecture (ADR-008).

Jamais de JSON brut Salesforce : chaque outil projette les champs utiles dans
un modèle stable, et conserve TOUJOURS l'`id` pour que l'agent puisse citer sa
source et enchaîner (get_opportunity, écritures ultérieures).
"""

from typing import Any

from pydantic import BaseModel


class AccountRef(BaseModel):
    id: str
    name: str | None = None
    industry: str | None = None
    phone: str | None = None
    website: str | None = None

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> "AccountRef":
        return cls(
            id=row["Id"],
            name=row.get("Name"),
            industry=row.get("Industry"),
            phone=row.get("Phone"),
            website=row.get("Website"),
        )


class ContactRef(BaseModel):
    id: str
    name: str | None = None
    email: str | None = None
    phone: str | None = None
    title: str | None = None
    account_id: str | None = None

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> "ContactRef":
        return cls(
            id=row["Id"],
            name=row.get("Name"),
            email=row.get("Email"),
            phone=row.get("Phone"),
            title=row.get("Title"),
            account_id=row.get("AccountId"),
        )


class OpportunityInfo(BaseModel):
    id: str
    name: str | None = None
    stage: str | None = None
    amount: float | None = None
    close_date: str | None = None
    account_id: str | None = None

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> "OpportunityInfo":
        amount = row.get("Amount")
        return cls(
            id=row["Id"],
            name=row.get("Name"),
            stage=row.get("StageName"),
            amount=float(amount) if amount is not None else None,
            close_date=row.get("CloseDate"),
            account_id=row.get("AccountId"),
        )


class ActivityInfo(BaseModel):
    id: str
    type: str  # "Task" | "Event"
    subject: str | None = None
    date: str | None = None
    status: str | None = None

    @classmethod
    def from_row(cls, row: dict[str, Any], type: str) -> "ActivityInfo":
        return cls(
            id=row["Id"],
            type=type,
            subject=row.get("Subject"),
            date=row.get("ActivityDate"),
            status=row.get("Status"),
        )


class CaseInfo(BaseModel):
    id: str
    case_number: str | None = None
    subject: str | None = None
    status: str | None = None
    priority: str | None = None

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> "CaseInfo":
        return cls(
            id=row["Id"],
            case_number=row.get("CaseNumber"),
            subject=row.get("Subject"),
            status=row.get("Status"),
            priority=row.get("Priority"),
        )


class AccountContext(BaseModel):
    """Tout le contexte d'un compte en un seul aller-retour (outil composite)."""

    account: AccountRef
    contacts: list[ContactRef]
    open_opportunities: list[OpportunityInfo]
    recent_activities: list[ActivityInfo]
    open_cases: list[CaseInfo]
