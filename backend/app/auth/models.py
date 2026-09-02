"""Tables du socle auth/tenancy (ADR-002, ADR-003).

`users` n'est volontairement PAS tenant-scopé : un utilisateur peut appartenir
à plusieurs organisations via `memberships` (rôle par organisation).
"""

import enum
import uuid

from sqlalchemy import Enum, ForeignKey, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class MembershipRole(enum.Enum):
    owner = "owner"
    admin = "admin"
    sales = "sales"
    hr = "hr"


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    name: Mapped[str] = mapped_column(String(200))
    slug: Mapped[str] = mapped_column(String(80), unique=True)


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    email: Mapped[str] = mapped_column(String(320), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(200))


class Membership(Base):
    """Association user <-> organization. PK composite (user_id, organization_id).

    `organization_id` fait partie de la PK (donc NOT NULL + indexé) : le mixin
    TenantScoped serait redondant ici, mais la table reste couverte par une
    politique RLS comme toute table portant organization_id.
    """

    __tablename__ = "memberships"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), primary_key=True
    )
    role: Mapped[MembershipRole] = mapped_column(
        Enum(MembershipRole, name="membership_role", values_callable=lambda e: [m.value for m in e])
    )
