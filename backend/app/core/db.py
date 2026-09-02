"""Socle SQLAlchemy 2 async : moteur, Base déclarative et mixin multi-locataire.

Le moteur runtime se connecte en `miara_app`, rôle SOUMIS aux politiques RLS
(FORCE ROW LEVEL SECURITY sur les tables à `organization_id`). Les migrations
utilisent `miara_admin` (voir alembic/env.py). Ne jamais utiliser le rôle
admin au runtime (carte CORE, section NE PAS).
"""

import uuid

from sqlalchemy import ForeignKey, MetaData
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, declared_attr, mapped_column

from app.config import settings

engine: AsyncEngine = create_async_engine(settings.DATABASE_URL, pool_pre_ping=True)
async_session: async_sessionmaker[AsyncSession] = async_sessionmaker(
    engine, expire_on_commit=False
)


class Base(DeclarativeBase):
    metadata = MetaData(
        naming_convention={
            "ix": "ix_%(column_0_label)s",
            "uq": "uq_%(table_name)s_%(column_0_name)s",
            "ck": "ck_%(table_name)s_%(constraint_name)s",
            "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
            "pk": "pk_%(table_name)s",
        }
    )


class TenantScoped:
    """`organization_id` NOT NULL + index. Obligatoire sur TOUTE table métier (ADR-002).

    L'isolation est garantie par la politique RLS PostgreSQL associée, pas par
    un filtre ORM : ne JAMAIS compter sur un `.where(organization_id == ...)`
    comme seule protection.
    """

    @declared_attr
    def organization_id(cls) -> Mapped[uuid.UUID]:  # noqa: N805
        return mapped_column(
            ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
