"""Moteur SQLAlchemy 2 async (asyncpg). Pas de modèles ici : le schéma métier
arrive avec la carte suivante (Base déclarative + RLS + Alembic autogenerate).
"""

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import settings

engine: AsyncEngine = create_async_engine(settings.DATABASE_URL, pool_pre_ping=True)
async_session: async_sessionmaker[AsyncSession] = async_sessionmaker(
    engine, expire_on_commit=False
)
