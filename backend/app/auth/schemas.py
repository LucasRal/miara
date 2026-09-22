"""Schémas Pydantic du module auth (entrées/sorties HTTP)."""

import uuid

from pydantic import BaseModel, EmailStr, Field

from app.auth.models import MembershipRole


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=1, max_length=200)


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class OrgCreateIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    slug: str | None = Field(default=None, max_length=80, pattern=r"^[a-z0-9]+(-[a-z0-9]+)*$")


class OrgOut(BaseModel):
    id: uuid.UUID
    name: str
    slug: str


class InviteIn(BaseModel):
    email: EmailStr
    role: MembershipRole


class MembershipOut(BaseModel):
    organization_id: uuid.UUID
    organization_name: str
    organization_slug: str
    role: MembershipRole


class RoleUpdateIn(BaseModel):
    role: MembershipRole


class MemberOut(BaseModel):
    """Un membre de l'organisation courante (page Paramètres)."""

    user_id: uuid.UUID
    email: str
    full_name: str
    role: MembershipRole


class MeOut(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    # Contexte actif (None tant qu'aucune organisation n'est rejointe/choisie).
    org_id: uuid.UUID | None
    role: MembershipRole | None
    memberships: list[MembershipOut]
