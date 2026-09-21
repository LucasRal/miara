"""FastAPI application entrypoint.

Wires configuration, CORS, structured logging, and the versioned API routers.
Business logic never lives here — each module (auth/hr/sales) exposes routers
that mount under /api/v1.
"""

import asyncio

from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware

from app.auth.router import router as auth_router
from app.config import settings
from app.core.health import check_broker, check_database, check_redis
from app.core.logging import configure_logging, request_id_middleware
from app.hr.jobs import router as hr_jobs_router
from app.sales.coaching import router as sales_coaching_router
from app.sales.conversations import router as sales_conversations_router
from app.sales.integrations import router as integrations_router
from app.sales.router import router as sales_router
from app.usage import router as usage_router

configure_logging()

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.API_VERSION,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.ALLOWED_ORIGINS.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.middleware("http")(request_id_middleware)

# Les routers des modules métier (auth, hr, sales) se montent ici sous /api/v1.
api_prefix = f"/api/{settings.API_VERSION}"
app.include_router(auth_router, prefix=api_prefix)
app.include_router(sales_router, prefix=api_prefix)
app.include_router(sales_conversations_router, prefix=api_prefix)
app.include_router(sales_coaching_router, prefix=api_prefix)
app.include_router(integrations_router, prefix=api_prefix)
app.include_router(hr_jobs_router, prefix=api_prefix)
app.include_router(usage_router, prefix=api_prefix)


@app.get("/health")
async def health_check(response: Response) -> dict[str, object]:
    """Sonde de vivacité non versionnée : BDD, broker (RabbitMQ) et Redis."""
    db_ok, broker_ok, redis_ok = await asyncio.gather(
        check_database(), check_broker(), check_redis()
    )
    checks = {
        "database": "ok" if db_ok else "error",
        "broker": "ok" if broker_ok else "error",
        "redis": "ok" if redis_ok else "error",
    }
    healthy = db_ok and broker_ok and redis_ok
    if not healthy:
        response.status_code = 503
    return {"status": "healthy" if healthy else "degraded", "checks": checks}
