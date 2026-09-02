"""Vérifications de disponibilité des dépendances d'infrastructure.

Chaque check renvoie True/False sans lever : le endpoint /health agrège et
répond 200 seulement si BDD, broker ET Redis sont joignables.
"""

import asyncio

import redis.asyncio as aioredis
from kombu import Connection
from sqlalchemy import text

from app.config import settings
from app.core.db import engine


async def check_database() -> bool:
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def _check_broker_sync() -> bool:
    try:
        with Connection(settings.RABBITMQ_URL, connect_timeout=3) as conn:
            conn.connect()
        return True
    except Exception:
        return False


async def check_broker() -> bool:
    # kombu est synchrone : on ne bloque pas la boucle événementielle.
    return await asyncio.to_thread(_check_broker_sync)


async def check_redis() -> bool:
    client = aioredis.from_url(settings.REDIS_URL)
    try:
        await client.ping()
        return True
    except Exception:
        return False
    finally:
        await client.aclose()
